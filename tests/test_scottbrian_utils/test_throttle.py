"""test_throttle.py module."""

import pytest
import math
import time
from typing import Any, cast, List, Tuple, Union

import threading

from scottbrian_utils.flower_box import print_flower_box_msg as flowers

from scottbrian_utils.throttle import Throttle, throttle
from scottbrian_utils.throttle import IncorrectRequestsSpecified
from scottbrian_utils.throttle import IncorrectSecondsSpecified
from scottbrian_utils.throttle import IncorrectModeSpecified
from scottbrian_utils.throttle import IncorrectAsyncQSizeSpecified
from scottbrian_utils.throttle import AsyncQSizeNotAllowed
from scottbrian_utils.throttle import IncorrectEarlyCountSpecified
from scottbrian_utils.throttle import MissingEarlyCountSpecification
from scottbrian_utils.throttle import EarlyCountNotAllowed
from scottbrian_utils.throttle import IncorrectLbThresholdSpecified
from scottbrian_utils.throttle import MissingLbThresholdSpecification
from scottbrian_utils.throttle import LbThresholdNotAllowed
from scottbrian_utils.throttle import AttemptedShutdownForSyncThrottle


###############################################################################
# Throttle test exceptions
###############################################################################
class ErrorTstThrottle(Exception):
    """Base class for exception in this module."""
    pass


class InvalidRouteNum(ErrorTstThrottle):
    """InvalidRouteNum exception class."""
    pass


class InvalidModeNum(ErrorTstThrottle):
    """InvalidModeNum exception class."""
    pass


class BadRequestStyleArg(ErrorTstThrottle):
    """BadRequestStyleArg exception class."""
    pass


###############################################################################
# requests_arg fixture
###############################################################################
requests_arg_list = [1, 2, 3]


@pytest.fixture(params=requests_arg_list)  # type: ignore
def requests_arg(request: Any) -> int:
    """Using different requests.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


###############################################################################
# seconds_arg fixture
###############################################################################
seconds_arg_list = [0.1, 0.5, 1, 2]


@pytest.fixture(params=seconds_arg_list)  # type: ignore
def seconds_arg(request: Any) -> Union[int, float]:
    """Using different seconds.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(Union[int, float], request.param)


###############################################################################
# mode_arg fixture
###############################################################################
mode_arg_list = [Throttle.MODE_ASYNC,
                 Throttle.MODE_SYNC,
                 Throttle.MODE_SYNC_LB,
                 Throttle.MODE_SYNC_EC]


@pytest.fixture(params=mode_arg_list)  # type: ignore
def mode_arg(request: Any) -> int:
    """Using different modes.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


###############################################################################
# mode_arg fixture
###############################################################################
lb_threshold_arg_list = [0.1, 1, 1.5, 3]


@pytest.fixture(params=lb_threshold_arg_list)  # type: ignore
def lb_threshold_arg(request: Any) -> Union[int, float]:
    """Using different lb_threshold values.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(Union[int, float], request.param)


###############################################################################
# early_count_arg fixture
###############################################################################
early_count_arg_list = [1, 2, 3]


@pytest.fixture(params=early_count_arg_list)  # type: ignore
def early_count_arg(request: Any) -> int:
    """Using different early_count values.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


###############################################################################
# send_interval_mult_arg fixture
###############################################################################
send_interval_mult_arg_list = [0.0, 0.3, 0.9, 1.0, 1.1]


@pytest.fixture(params=send_interval_mult_arg_list)  # type: ignore
def send_interval_mult_arg(request: Any) -> float:
    """Using different send rates.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(float, request.param)


###############################################################################
# request_style_arg fixture
###############################################################################
request_style_arg_list = [0, 1, 2, 3, 4, 5, 6]


@pytest.fixture(params=request_style_arg_list)  # type: ignore
def request_style_arg(request: Any) -> int:
    """Using different early_count values.

    Args:
        request: special fixture that returns the fixture params

    Returns:
        The params values are returned one at a time
    """
    return cast(int, request.param)


###############################################################################
# TestThrottleBasic class to test Throttle methods
###############################################################################
class TestThrottleErrors:
    """TestThrottle class."""
    def test_throttle_bad_args(self) -> None:
        """test_throttle using bad arguments."""
        #######################################################################
        # bad requests
        #######################################################################
        with pytest.raises(IncorrectRequestsSpecified):
            _ = Throttle(requests=0,
                         seconds=1,
                         mode=Throttle.MODE_ASYNC)
        with pytest.raises(IncorrectRequestsSpecified):
            _ = Throttle(requests=-1,
                         seconds=1,
                         mode=Throttle.MODE_ASYNC)
        with pytest.raises(IncorrectRequestsSpecified):
            _ = Throttle(requests='1',  # type: ignore
                         seconds=1,
                         mode=Throttle.MODE_ASYNC)

        #######################################################################
        # bad seconds
        #######################################################################
        with pytest.raises(IncorrectSecondsSpecified):
            _ = Throttle(requests=1,
                         seconds=0,
                         mode=Throttle.MODE_ASYNC)
        with pytest.raises(IncorrectSecondsSpecified):
            _ = Throttle(requests=1,
                         seconds=-1,
                         mode=Throttle.MODE_ASYNC)
        with pytest.raises(IncorrectSecondsSpecified):
            _ = Throttle(requests=1,
                         seconds='1',  # type: ignore
                         mode=Throttle.MODE_ASYNC)

        #######################################################################
        # bad mode
        #######################################################################
        with pytest.raises(IncorrectModeSpecified):
            _ = Throttle(requests=1,
                         seconds=1,
                         mode=-1)
        with pytest.raises(IncorrectModeSpecified):
            _ = Throttle(requests=1,
                         seconds=1,
                         mode=0)
        with pytest.raises(IncorrectModeSpecified):
            _ = Throttle(requests=1,
                         seconds=1,
                         mode=Throttle.MODE_MAX+1)
        with pytest.raises(IncorrectModeSpecified):
            _ = Throttle(requests=1,
                         seconds=1,
                         mode='1')  # type: ignore

        #######################################################################
        # bad async_q_size
        #######################################################################
        with pytest.raises(IncorrectAsyncQSizeSpecified):
            _ = Throttle(requests=1,
                         seconds=1,
                         mode=Throttle.MODE_ASYNC,
                         async_q_size=-1)
        with pytest.raises(IncorrectAsyncQSizeSpecified):
            _ = Throttle(requests=1,
                         seconds=1,
                         mode=Throttle.MODE_ASYNC,
                         async_q_size=0)
        with pytest.raises(IncorrectAsyncQSizeSpecified):
            _ = Throttle(requests=1,
                         seconds=1,
                         mode=Throttle.MODE_ASYNC,
                         async_q_size='1')  # type: ignore
        with pytest.raises(AsyncQSizeNotAllowed):
            _ = Throttle(requests=1,
                         seconds=1,
                         mode=Throttle.MODE_SYNC,
                         async_q_size=256)
        with pytest.raises(AsyncQSizeNotAllowed):
            _ = Throttle(requests=1,
                         seconds=1,
                         mode=Throttle.MODE_SYNC_EC,
                         async_q_size=256,
                         early_count=3)
        with pytest.raises(AsyncQSizeNotAllowed):
            _ = Throttle(requests=1,
                         seconds=1,
                         mode=Throttle.MODE_SYNC_LB,
                         async_q_size=256,
                         lb_threshold=3)
        #######################################################################
        # bad early_count
        #######################################################################
        with pytest.raises(EarlyCountNotAllowed):
            _ = Throttle(requests=1,
                         seconds=1,
                         mode=Throttle.MODE_ASYNC,
                         early_count=0)
        with pytest.raises(EarlyCountNotAllowed):
            _ = Throttle(requests=1,
                         seconds=1,
                         mode=Throttle.MODE_SYNC,
                         early_count=1)
        with pytest.raises(MissingEarlyCountSpecification):
            _ = Throttle(requests=1,
                         seconds=1,
                         mode=Throttle.MODE_SYNC_EC)
        with pytest.raises(EarlyCountNotAllowed):
            _ = Throttle(requests=1,
                         seconds=1,
                         mode=Throttle.MODE_SYNC_LB,
                         early_count=1)
        with pytest.raises(IncorrectEarlyCountSpecified):
            _ = Throttle(requests=1,
                         seconds=1,
                         mode=Throttle.MODE_SYNC_EC,
                         early_count=-1)
        with pytest.raises(IncorrectEarlyCountSpecified):
            _ = Throttle(requests=1,
                         seconds=1,
                         mode=Throttle.MODE_SYNC_EC,
                         early_count='1')  # type: ignore
        #######################################################################
        # bad lb_threshold
        #######################################################################
        with pytest.raises(LbThresholdNotAllowed):
            _ = Throttle(requests=1,
                         seconds=1,
                         mode=Throttle.MODE_ASYNC,
                         lb_threshold=1)
        with pytest.raises(LbThresholdNotAllowed):
            _ = Throttle(requests=1,
                         seconds=1,
                         mode=Throttle.MODE_SYNC,
                         lb_threshold=0)
        with pytest.raises(LbThresholdNotAllowed):
            _ = Throttle(requests=1,
                         seconds=1,
                         mode=Throttle.MODE_SYNC_EC,
                         early_count=3,
                         lb_threshold=0)
        with pytest.raises(MissingLbThresholdSpecification):
            _ = Throttle(requests=1,
                         seconds=1,
                         mode=Throttle.MODE_SYNC_LB)
        with pytest.raises(IncorrectLbThresholdSpecified):
            _ = Throttle(requests=1,
                         seconds=1,
                         mode=Throttle.MODE_SYNC_LB,
                         lb_threshold=-1)
        with pytest.raises(IncorrectLbThresholdSpecified):
            _ = Throttle(requests=1,
                         seconds=1,
                         mode=Throttle.MODE_SYNC_LB,
                         lb_threshold='1')  # type: ignore


###############################################################################
# TestThrottleBasic class to test Throttle methods
###############################################################################
class TestThrottleBasic:
    """Test basic functions of Throttle."""

    ###########################################################################
    # len checks
    ###########################################################################
    def test_throttle_len_async(self,
                                requests_arg: int,
                                mode_arg: int
                                ) -> None:
        """Test the len of async throttle.

        Args:
            requests_arg: fixture that provides args
            mode_arg: throttle mode to use

        Raises:
            InvalidModeNum: Mode invalid
        """
        # create a throttle with a long enough interval to ensure that we
        # can populate the async_q and get the length before we start
        # dequeing requests from it
        print('mode_arg:', mode_arg)
        if mode_arg == Throttle.MODE_ASYNC:
            a_throttle = Throttle(requests=requests_arg,
                                  seconds=requests_arg * 3,  # 3 sec interval
                                  mode=Throttle.MODE_ASYNC)
        elif mode_arg == Throttle.MODE_SYNC:
            a_throttle = Throttle(requests=requests_arg,
                                  seconds=1,
                                  mode=Throttle.MODE_SYNC)
        elif mode_arg == Throttle.MODE_SYNC_EC:
            a_throttle = Throttle(requests=requests_arg,
                                  seconds=1,
                                  mode=Throttle.MODE_SYNC_EC,
                                  early_count=3)
        elif mode_arg == Throttle.MODE_SYNC_LB:
            a_throttle = Throttle(requests=requests_arg,
                                  seconds=1,
                                  mode=Throttle.MODE_SYNC_LB,
                                  lb_threshold=2)
        else:
            raise InvalidModeNum('Mode invalid')

        def dummy_func(an_event: threading.Event) -> None:
            an_event.set()

        event = threading.Event()

        for i in range(requests_arg):
            a_throttle.send_request(dummy_func, event)

        event.wait()
        # assert is for 1 less than queued because the first request
        # will be scheduled immediately
        if mode_arg == Throttle.MODE_ASYNC:
            assert len(a_throttle) == requests_arg - 1
            # start_shutdown will return when the request_q cleanup is complete
            a_throttle.start_shutdown()
            assert len(a_throttle) == 0
        else:
            assert len(a_throttle) == 0

    def test_throttle_len_sync(self,
                               requests_arg: int
                               ) -> None:
        """Test the len of sync throttle.

        Args:
            requests_arg: fixture that provides args

        """
        # create a sync throttle
        a_throttle = Throttle(requests=requests_arg,
                              seconds=requests_arg * 3,  # 3 second interval
                              mode=Throttle.MODE_SYNC)

        def dummy_func() -> None:
            pass

        for i in range(requests_arg):
            a_throttle.send_request(dummy_func)

        # assert is for 0 since sync mode does not have an async_q

        assert len(a_throttle) == 0

    ###########################################################################
    # task done check
    ###########################################################################
    # def test_throttle_task_done(self,
    #                             requests_arg: int
    #                             ) -> None:
    #     """Test task done for throttle throttle.
    #
    #     Args:
    #         requests_arg: fixture that provides args
    #
    #     """
    #     # create a throttle with a short interval
    #     a_throttle = Throttle(requests=requests_arg,
    #                           seconds=requests_arg * 0.25,  #  1/4 interval
    #                           mode=Throttle.MODE_ASYNC)
    #
    #     class Counts:
    #         def __init__(self):
    #             self.count = 0
    #
    #     a_counts = Counts()
    #
    #     def dummy_func(counts) -> None:
    #         counts.count += 1
    #
    #     for i in range(requests_arg):
    #          a_throttle.send_request(dummy_func, a_counts)
    #
    #     a_throttle.async_q.join()
    #     assert len(a_throttle) == 0
    #     assert a_counts.count == requests_arg
    #     # start_shutdown to end the scheduler thread
    #     a_throttle.start_shutdown()
    #     assert len(a_throttle) == 0

    ###########################################################################
    # repr with mode async
    ###########################################################################
    def test_throttle_repr_async(self,
                                 requests_arg: int,
                                 seconds_arg: Union[int, float]
                                 ) -> None:
        """test_throttle repr mode 1 with various requests and seconds.

        Args:
            requests_arg: fixture that provides args
            seconds_arg: fixture that provides args

        """
        #######################################################################
        # throttle with async_q_size specified
        #######################################################################
        a_throttle = Throttle(requests=requests_arg,
                              seconds=seconds_arg,
                              mode=Throttle.MODE_ASYNC)

        expected_repr_str = \
            f'Throttle(' \
            f'requests={requests_arg}, ' \
            f'seconds={float(seconds_arg)}, ' \
            f'mode=Throttle.MODE_ASYNC, ' \
            f'async_q_size={Throttle.DEFAULT_ASYNC_Q_SIZE})'

        assert repr(a_throttle) == expected_repr_str

        a_throttle.start_shutdown()

        #######################################################################
        # throttle with async_q_size specified
        #######################################################################
        q_size = requests_arg * 3
        a_throttle = Throttle(requests=requests_arg,
                              seconds=seconds_arg,
                              mode=Throttle.MODE_ASYNC,
                              async_q_size=q_size)

        expected_repr_str = \
            f'Throttle(' \
            f'requests={requests_arg}, ' \
            f'seconds={float(seconds_arg)}, ' \
            f'mode=Throttle.MODE_ASYNC, ' \
            f'async_q_size={q_size})'

        assert repr(a_throttle) == expected_repr_str

        a_throttle.start_shutdown()

    ###########################################################################
    # repr with mode sync
    ###########################################################################
    def test_throttle_repr_sync(self,
                                requests_arg: int,
                                seconds_arg: Union[int, float],
                                ) -> None:
        """test_throttle repr mode 2 with various requests and seconds.

        Args:
            requests_arg: fixture that provides args
            seconds_arg: fixture that provides args
        """
        a_throttle = Throttle(requests=requests_arg,
                              seconds=seconds_arg,
                              mode=Throttle.MODE_SYNC)

        expected_repr_str = \
            f'Throttle(' \
            f'requests={requests_arg}, ' \
            f'seconds={float(seconds_arg)}, ' \
            f'mode=Throttle.MODE_SYNC)'

        assert repr(a_throttle) == expected_repr_str

    ###########################################################################
    # repr with mode sync early count
    ###########################################################################
    def test_throttle_repr_sync_ec(self,
                                   requests_arg: int,
                                   seconds_arg: Union[int, float],
                                   early_count_arg: int,
                                   ) -> None:
        """test_throttle repr mode 2 with various requests and seconds.

        Args:
            requests_arg: fixture that provides args
            seconds_arg: fixture that provides args
            early_count_arg: fixture that provides args
        """
        a_throttle = Throttle(requests=requests_arg,
                              seconds=seconds_arg,
                              mode=Throttle.MODE_SYNC_EC,
                              early_count=early_count_arg)

        expected_repr_str = \
            f'Throttle(' \
            f'requests={requests_arg}, ' \
            f'seconds={float(seconds_arg)}, ' \
            f'mode=Throttle.MODE_SYNC_EC, ' \
            f'early_count={early_count_arg})'

        assert repr(a_throttle) == expected_repr_str

    ###########################################################################
    # repr with mode sync leaky bucket
    ###########################################################################
    def test_throttle_repr_sync_lb(self,
                                   requests_arg: int,
                                   seconds_arg: Union[int, float],
                                   lb_threshold_arg: Union[int, float],
                                   ) -> None:
        """test_throttle repr with various requests and seconds.

        Args:
            requests_arg: fixture that provides args
            seconds_arg: fixture that provides args
            lb_threshold_arg: fixture that provides args
        """
        a_throttle = Throttle(requests=requests_arg,
                              seconds=seconds_arg,
                              mode=Throttle.MODE_SYNC_LB,
                              lb_threshold=lb_threshold_arg)

        expected_repr_str = \
            f'Throttle(' \
            f'requests={requests_arg}, ' \
            f'seconds={float(seconds_arg)}, ' \
            f'mode=Throttle.MODE_SYNC_LB, ' \
            f'lb_threshold={float(lb_threshold_arg)})'

        assert repr(a_throttle) == expected_repr_str


###############################################################################
# TestThrottleDecoratorErrors class
###############################################################################
class TestThrottleDecoratorErrors:
    """TestThrottleDecoratorErrors class."""
    def test_pie_throttle_bad_args(self) -> None:
        """test_throttle using bad arguments."""
        #######################################################################
        # bad requests
        #######################################################################
        with pytest.raises(IncorrectRequestsSpecified):
            @throttle(requests=0, seconds=1, mode=Throttle.MODE_ASYNC)
            def f1() -> None:
                print('42')
            f1()

        with pytest.raises(IncorrectRequestsSpecified):
            @throttle(requests=-1, seconds=1, mode=Throttle.MODE_ASYNC)
            def f1() -> None:
                print('42')
            f1()

        with pytest.raises(IncorrectRequestsSpecified):
            @throttle(requests='1', seconds=1,  # type: ignore
                      mode=Throttle.MODE_ASYNC)
            def f1() -> None:
                print('42')
            f1()
        #######################################################################
        # bad seconds
        #######################################################################
        with pytest.raises(IncorrectSecondsSpecified):
            @throttle(requests=1, seconds=0, mode=Throttle.MODE_ASYNC)
            def f1() -> None:
                print('42')
            f1()

        with pytest.raises(IncorrectSecondsSpecified):
            @throttle(requests=1, seconds=-1, mode=Throttle.MODE_ASYNC)
            def f1() -> None:
                print('42')
            f1()
        with pytest.raises(IncorrectSecondsSpecified):
            @throttle(requests=1, seconds='1',  # type: ignore
                      mode=Throttle.MODE_ASYNC)
            def f1() -> None:
                print('42')
            f1()

        #######################################################################
        # bad mode
        #######################################################################
        with pytest.raises(IncorrectModeSpecified):
            @throttle(requests=1,
                      seconds=1,
                      mode=-1)
            def f1() -> None:
                print('42')
            f1()
        with pytest.raises(IncorrectModeSpecified):
            @throttle(requests=1,
                      seconds=1,
                      mode=0)
            def f1() -> None:
                print('42')
            f1()
        with pytest.raises(IncorrectModeSpecified):
            @throttle(requests=1,
                      seconds=1,
                      mode=Throttle.MODE_MAX+1)
            def f1() -> None:
                print('42')
            f1()
        with pytest.raises(IncorrectModeSpecified):
            @throttle(requests=1,
                      seconds=1,
                      mode='1')  # type: ignore
            def f1() -> None:
                print('42')
            f1()

        #######################################################################
        # bad async_q_size
        #######################################################################
        with pytest.raises(IncorrectAsyncQSizeSpecified):
            @throttle(requests=1,
                      seconds=1,
                      mode=Throttle.MODE_ASYNC,
                      async_q_size=-1)
            def f1() -> None:
                print('42')
            f1()
        with pytest.raises(IncorrectAsyncQSizeSpecified):
            @throttle(requests=1,
                      seconds=1,
                      mode=Throttle.MODE_ASYNC,
                      async_q_size=0)
            def f1() -> None:
                print('42')
            f1()
        with pytest.raises(IncorrectAsyncQSizeSpecified):
            @throttle(requests=1,
                      seconds=1,
                      mode=Throttle.MODE_ASYNC,
                      async_q_size='1')  # type: ignore
            def f1() -> None:
                print('42')
            f1()
        with pytest.raises(AsyncQSizeNotAllowed):
            @throttle(requests=1,
                      seconds=1,
                      mode=Throttle.MODE_SYNC,
                      async_q_size=256)
            def f1() -> None:
                print('42')
            f1()
        with pytest.raises(AsyncQSizeNotAllowed):
            @throttle(requests=1,
                      seconds=1,
                      mode=Throttle.MODE_SYNC_EC,
                      async_q_size=256,
                      early_count=3)
            def f1() -> None:
                print('42')
            f1()
        with pytest.raises(AsyncQSizeNotAllowed):
            @throttle(requests=1,
                      seconds=1,
                      mode=Throttle.MODE_SYNC_LB,
                      async_q_size=256,
                      lb_threshold=3)
            def f1() -> None:
                print('42')
            f1()

        #######################################################################
        # bad early_count
        #######################################################################
        with pytest.raises(EarlyCountNotAllowed):
            @throttle(requests=1,
                      seconds=1,
                      mode=Throttle.MODE_ASYNC,
                      early_count=1)
            def f1() -> None:
                print('42')
            f1()
        with pytest.raises(EarlyCountNotAllowed):
            @throttle(requests=1,
                      seconds=1,
                      mode=Throttle.MODE_SYNC,
                      early_count=1)
            def f1() -> None:
                print('42')
            f1()
        with pytest.raises(MissingEarlyCountSpecification):
            @throttle(requests=1,
                      seconds=1,
                      mode=Throttle.MODE_SYNC_EC)
            def f1() -> None:
                print('42')
            f1()
        with pytest.raises(EarlyCountNotAllowed):
            @throttle(requests=1,
                      seconds=1,
                      mode=Throttle.MODE_SYNC_LB,
                      early_count=1)
            def f1() -> None:
                print('42')
            f1()
        with pytest.raises(IncorrectEarlyCountSpecified):
            @throttle(requests=1,
                      seconds=1,
                      mode=Throttle.MODE_SYNC_EC,
                      early_count=-1)
            def f1() -> None:
                print('42')
            f1()
        with pytest.raises(IncorrectEarlyCountSpecified):
            @throttle(requests=1,
                      seconds=1,
                      mode=Throttle.MODE_SYNC_EC,
                      early_count='1')  # type: ignore
            def f1() -> None:
                print('42')
            f1()
        #######################################################################
        # bad lb_threshold
        #######################################################################
        with pytest.raises(LbThresholdNotAllowed):
            @throttle(requests=1,
                      seconds=1,
                      mode=Throttle.MODE_ASYNC,
                      lb_threshold=1)
            def f1() -> None:
                print('42')
            f1()
        with pytest.raises(LbThresholdNotAllowed):
            @throttle(requests=1,
                      seconds=1,
                      mode=Throttle.MODE_SYNC,
                      lb_threshold=1)
            def f1() -> None:
                print('42')
            f1()
        with pytest.raises(LbThresholdNotAllowed):
            @throttle(requests=1,
                      seconds=1,
                      mode=Throttle.MODE_SYNC_EC,
                      early_count=5,
                      lb_threshold=0)
            def f1() -> None:
                print('42')
            f1()
        with pytest.raises(MissingLbThresholdSpecification):
            @throttle(requests=1,
                      seconds=1,
                      mode=Throttle.MODE_SYNC_LB)
            def f1() -> None:
                print('42')
            f1()
        with pytest.raises(IncorrectLbThresholdSpecified):
            @throttle(requests=1,
                      seconds=1,
                      mode=Throttle.MODE_SYNC_LB,
                      lb_threshold=-1)
            def f1() -> None:
                print('42')
            f1()
        with pytest.raises(IncorrectLbThresholdSpecified):
            @throttle(requests=1,
                      seconds=1,
                      mode=Throttle.MODE_SYNC_LB,
                      lb_threshold='1')  # type: ignore
            def f1() -> None:
                print('42')
            f1()


###############################################################################
# TestThrottle class
###############################################################################
class TestThrottle:
    """Class TestThrottle.

    The following section tests each combination of arguments to the throttle.

    For the decorator, there are three styles of decoration (using pie,
    calling with the function as the first parameter, and calling the
    decorator with the function specified after the call. This test is
    especially useful to ensure that the type hints are working correctly,
    and that all combinations are accepted by python.

    The non-decorator cases will be simpler, with the exception of
    doing some explicit calls to shutdown the throttle (which is not possible
    with the decorator style - for this, we can set the start_shutdown_event.

    The following keywords with various values and in all combinations are
    tested:
        requests - various increments
        seconds - various increments, both int and float
        throttle_enabled - true/false

    """
    ###########################################################################
    # test_throttle_async
    ###########################################################################
    def test_throttle_async(self,
                            requests_arg: int,
                            seconds_arg: Union[int, float],
                            send_interval_mult_arg: float,
                            request_style_arg: int
                            ) -> None:
        """Method to start throttle mode1 tests.

        Args:
            requests_arg: number of requests per interval from fixture
            seconds_arg: interval for number of requests from fixture
            send_interval_mult_arg: interval between each send of a request
            request_style_arg: chooses function args mix
        """
        send_interval = (seconds_arg / requests_arg) * send_interval_mult_arg
        self.throttle_router(requests=requests_arg,
                             seconds=seconds_arg,
                             mode=Throttle.MODE_ASYNC,
                             early_count=0,
                             lb_threshold=0,
                             send_interval=send_interval,
                             request_style=request_style_arg)

    ###########################################################################
    # test_throttle_sync
    ###########################################################################
    def test_throttle_sync(self,
                           requests_arg: int,
                           seconds_arg: Union[int, float],
                           early_count_arg: int,
                           send_interval_mult_arg: float,
                           request_style_arg: int
                           ) -> None:
        """Method to start throttle sync tests.

        Args:
            requests_arg: number of requests per interval from fixture
            seconds_arg: interval for number of requests from fixture
            early_count_arg: count used for sync with early count algo
            send_interval_mult_arg: interval between each send of a request
            request_style_arg: chooses function args mix
        """
        send_interval = (seconds_arg / requests_arg) * send_interval_mult_arg
        self.throttle_router(requests=requests_arg,
                             seconds=seconds_arg,
                             mode=Throttle.MODE_SYNC_EC,
                             early_count=0,
                             lb_threshold=0,
                             send_interval=send_interval,
                             request_style=request_style_arg)

    ###########################################################################
    # test_throttle_sync_ec
    ###########################################################################
    def test_throttle_sync_ec(self,
                              requests_arg: int,
                              seconds_arg: Union[int, float],
                              early_count_arg: int,
                              send_interval_mult_arg: float,
                              request_style_arg: int
                              ) -> None:
        """Method to start throttle sync_ec tests.

        Args:
            requests_arg: number of requests per interval from fixture
            seconds_arg: interval for number of requests from fixture
            early_count_arg: count used for sync with early count algo
            send_interval_mult_arg: interval between each send of a request
            request_style_arg: chooses function args mix
        """
        send_interval = (seconds_arg / requests_arg) * send_interval_mult_arg
        self.throttle_router(requests=requests_arg,
                             seconds=seconds_arg,
                             mode=Throttle.MODE_SYNC_EC,
                             early_count=early_count_arg,
                             lb_threshold=0,
                             send_interval=send_interval,
                             request_style=request_style_arg)

    ###########################################################################
    # test_throttle_sync_lb
    ###########################################################################
    def test_throttle_sync_lb(self,
                              requests_arg: int,
                              seconds_arg: Union[int, float],
                              lb_threshold_arg: Union[int, float],
                              send_interval_mult_arg: float,
                              request_style_arg: int
                              ) -> None:
        """Method to start throttle sync_lb tests.

        Args:
            requests_arg: number of requests per interval from fixture
            seconds_arg: interval for number of requests from fixture
            lb_threshold_arg: threshold used with sync leaky bucket algo
            send_interval_mult_arg: interval between each send of a request
            request_style_arg: chooses function args mix
        """
        send_interval = (seconds_arg / requests_arg) * send_interval_mult_arg
        self.throttle_router(requests=requests_arg,
                             seconds=seconds_arg,
                             mode=Throttle.MODE_SYNC_LB,
                             early_count=0,
                             lb_threshold=lb_threshold_arg,
                             send_interval=send_interval,
                             request_style=request_style_arg)

    ###########################################################################
    # throttle_router
    ###########################################################################
    def throttle_router(self,
                        requests: int,
                        seconds: Union[int, float],
                        mode: int,
                        early_count: int,
                        lb_threshold: Union[int, float],
                        send_interval: float,
                        request_style: int
                        ) -> None:
        """Method test_throttle_router.

        Args:
            requests: number of requests per interval
            seconds: interval for number of requests
            mode: async or sync_EC or sync_LB
            early_count: count used for sync with early count algo
            lb_threshold: threshold used with sync leaky bucket algo
            send_interval: interval between each send of a request
            request_style: chooses function args mix

        Raises:
            BadRequestStyleArg: The request style arg must be 0 to 6
            InvalidModeNum: The Mode must be 1, 2, 3, or 4
        """
        request_multiplier = 32
        #######################################################################
        # Instantiate Throttle
        #######################################################################
        if mode == Throttle.MODE_ASYNC:
            a_throttle = Throttle(requests=requests,
                                  seconds=seconds,
                                  mode=Throttle.MODE_ASYNC,
                                  async_q_size=(requests
                                                * request_multiplier)
                                  )
        elif mode == Throttle.MODE_SYNC:
            a_throttle = Throttle(requests=requests,
                                  seconds=seconds,
                                  mode=Throttle.MODE_SYNC
                                  )
        elif mode == Throttle.MODE_SYNC_EC:
            a_throttle = Throttle(requests=requests,
                                  seconds=seconds,
                                  mode=Throttle.MODE_SYNC_EC,
                                  early_count=early_count
                                  )
        elif mode == Throttle.MODE_SYNC_LB:
            a_throttle = Throttle(requests=requests,
                                  seconds=seconds,
                                  mode=Throttle.MODE_SYNC_LB,
                                  lb_threshold=lb_threshold
                                  )
        else:
            raise InvalidModeNum('The Mode must be 1, 2, 3, or 4')

        #######################################################################
        # Instantiate Request Validator
        #######################################################################
        request_validator = RequestValidator(requests=requests,
                                             seconds=seconds,
                                             mode=mode,
                                             early_count=early_count,
                                             lb_threshold=lb_threshold,
                                             request_mult=request_multiplier,
                                             send_interval=send_interval)

        #######################################################################
        # Make requests and validate
        #######################################################################
        if request_style == 0:
            for i in range(requests * request_multiplier):
                # 0
                rc = a_throttle.send_request(request_validator.request0)
                if mode == Throttle.MODE_ASYNC:
                    assert rc is Throttle.RC_OK
                else:
                    assert rc == i
                time.sleep(send_interval)

            if mode == Throttle.MODE_ASYNC:
                a_throttle.start_shutdown(
                    shutdown_type=Throttle.TYPE_SHUTDOWN_SOFT)

            request_validator.validate_series()  # validate for the series

        elif request_style == 1:
            for i in range(requests * request_multiplier):
                # 1
                rc = a_throttle.send_request(request_validator.request1, i)
                exp_rc = i if mode != Throttle.MODE_ASYNC else Throttle.RC_OK
                assert rc == exp_rc
                time.sleep(send_interval)

            if mode == Throttle.MODE_ASYNC:
                a_throttle.start_shutdown(
                    shutdown_type=Throttle.TYPE_SHUTDOWN_SOFT)
            request_validator.validate_series()  # validate for the series

        elif request_style == 2:
            for i in range(requests * request_multiplier):
                # 2
                rc = a_throttle.send_request(request_validator.request2,
                                             i,
                                             requests)
                exp_rc = i if mode != Throttle.MODE_ASYNC else Throttle.RC_OK
                assert rc == exp_rc
                time.sleep(send_interval)

            if mode == Throttle.MODE_ASYNC:
                a_throttle.start_shutdown(
                    shutdown_type=Throttle.TYPE_SHUTDOWN_SOFT)
            request_validator.validate_series()  # validate for the series

        elif request_style == 3:
            for i in range(requests * request_multiplier):
                # 3
                rc = a_throttle.send_request(request_validator.request3, idx=i)
                exp_rc = i if mode != Throttle.MODE_ASYNC else Throttle.RC_OK
                assert rc == exp_rc
                time.sleep(send_interval)

            if mode == Throttle.MODE_ASYNC:
                a_throttle.start_shutdown(
                    shutdown_type=Throttle.TYPE_SHUTDOWN_SOFT)
            request_validator.validate_series()  # validate for the series

        elif request_style == 4:
            for i in range(requests * request_multiplier):
                # 4
                rc = a_throttle.send_request(request_validator.request4,
                                             idx=i,
                                             seconds=seconds)
                exp_rc = i if mode != Throttle.MODE_ASYNC else Throttle.RC_OK
                assert rc == exp_rc
                time.sleep(send_interval)

            if mode == Throttle.MODE_ASYNC:
                a_throttle.start_shutdown(
                    shutdown_type=Throttle.TYPE_SHUTDOWN_SOFT)
            request_validator.validate_series()  # validate for the series

        elif request_style == 5:
            for i in range(requests * request_multiplier):
                # 5
                rc = a_throttle.send_request(request_validator.request5,
                                             i,
                                             interval=send_interval)
                exp_rc = i if mode != Throttle.MODE_ASYNC else Throttle.RC_OK
                assert rc == exp_rc
                time.sleep(send_interval)

            if mode == Throttle.MODE_ASYNC:
                a_throttle.start_shutdown(
                    shutdown_type=Throttle.TYPE_SHUTDOWN_SOFT)
            request_validator.validate_series()  # validate for the series

        elif request_style == 6:
            for i in range(requests * request_multiplier):
                # 6
                rc = a_throttle.send_request(request_validator.request6,
                                             i,
                                             requests,
                                             seconds=seconds,
                                             interval=send_interval)
                exp_rc = i if mode != Throttle.MODE_ASYNC else Throttle.RC_OK
                assert rc == exp_rc
                time.sleep(send_interval)

            if mode == Throttle.MODE_ASYNC:
                a_throttle.start_shutdown(
                    shutdown_type=Throttle.TYPE_SHUTDOWN_SOFT)
            request_validator.validate_series()  # validate for the series

        else:
            raise BadRequestStyleArg('The request style arg must be 0 to 6')

    ###########################################################################
    # test_pie_throttle_async
    ###########################################################################
    def test_pie_throttle_async(self,
                                requests_arg: int,
                                seconds_arg: Union[int, float],
                                send_interval_mult_arg: float
                                ) -> None:
        """Method to start throttle mode1 tests.

        Args:
            requests_arg: number of requests per interval from fixture
            seconds_arg: interval for number of requests from fixture
            send_interval_mult_arg: interval between each send of a request
        """
        #######################################################################
        # Instantiate Request Validator
        #######################################################################
        request_multiplier = 32
        send_interval = (seconds_arg/requests_arg) * send_interval_mult_arg
        request_validator = RequestValidator(requests=requests_arg,
                                             seconds=seconds_arg,
                                             mode=Throttle.MODE_ASYNC,
                                             early_count=0,
                                             lb_threshold=0,
                                             request_mult=request_multiplier,
                                             send_interval=send_interval)

        #######################################################################
        # Decorate functions with throttle
        #######################################################################
        @throttle(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=Throttle.MODE_ASYNC)
        def f0() -> None:
            request_validator.callback0()

        @throttle(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=Throttle.MODE_ASYNC)
        def f1(idx: int) -> None:
            request_validator.callback1(idx)

        @throttle(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=Throttle.MODE_ASYNC)
        def f2(idx: int, requests: int) -> None:
            request_validator.callback2(idx, requests)

        @throttle(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=Throttle.MODE_ASYNC)
        def f3(*, idx: int) -> None:
            request_validator.callback3(idx=idx)

        @throttle(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=Throttle.MODE_ASYNC)
        def f4(*, idx: int, seconds: float) -> None:
            request_validator.callback4(idx=idx, seconds=seconds)

        @throttle(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=Throttle.MODE_ASYNC)
        def f5(idx: int, *, interval: float) -> None:
            request_validator.callback5(idx,
                                        interval=interval)

        @throttle(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=Throttle.MODE_ASYNC)
        def f6(idx: int, requests: int, *, seconds: float, interval: float
               ) -> None:
            request_validator.callback6(idx,
                                        requests,
                                        seconds=seconds,
                                        interval=interval)

        #######################################################################
        # Invoke the functions
        #######################################################################
        for i in range(requests_arg * request_multiplier):
            rc = f0()
            assert rc is None
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series
        f0.throttle.start_shutdown()

        for i in range(requests_arg * request_multiplier):
            rc = f1(i)
            assert rc is None
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series
        f1.throttle.start_shutdown()

        for i in range(requests_arg * request_multiplier):
            rc = f2(i, requests_arg)
            assert rc is None
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series
        f2.throttle.start_shutdown()

        for i in range(requests_arg * request_multiplier):
            rc = f3(idx=i)
            assert rc is None
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series
        f3.throttle.start_shutdown()

        for i in range(requests_arg * request_multiplier):
            rc = f4(idx=i, seconds=seconds_arg)
            assert rc is None
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series
        f4.throttle.start_shutdown()

        for i in range(requests_arg * request_multiplier):
            rc = f5(idx=i, interval=send_interval_mult_arg)
            assert rc is None
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series
        f5.throttle.start_shutdown()

        for i in range(requests_arg * request_multiplier):
            rc = f6(i, requests_arg,
                    seconds=seconds_arg, interval=send_interval_mult_arg)
            assert rc is None
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series
        f6.throttle.start_shutdown()

    ###########################################################################
    # test_throttle_sync
    ###########################################################################
    def test_pie_throttle_sync(self,
                               requests_arg: int,
                               seconds_arg: Union[int, float],
                               send_interval_mult_arg: float
                               ) -> None:
        """Method to start throttle sync tests.

        Args:
            requests_arg: number of requests per interval from fixture
            seconds_arg: interval for number of requests from fixture
            send_interval_mult_arg: interval between each send of a request
        """
        #######################################################################
        # Instantiate Request Validator
        #######################################################################
        request_multiplier = 32
        send_interval = (seconds_arg / requests_arg) * send_interval_mult_arg
        request_validator = RequestValidator(requests=requests_arg,
                                             seconds=seconds_arg,
                                             mode=Throttle.MODE_SYNC,
                                             early_count=0,
                                             lb_threshold=0,
                                             request_mult=request_multiplier,
                                             send_interval=send_interval)

        #######################################################################
        # Decorate functions with throttle
        #######################################################################
        @throttle(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=Throttle.MODE_SYNC)
        def f0() -> int:
            request_validator.callback0()
            return 42

        @throttle(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=Throttle.MODE_SYNC)
        def f1(idx: int) -> int:
            request_validator.callback1(idx)
            return idx + 42 + 1

        @throttle(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=Throttle.MODE_SYNC)
        def f2(idx: int, requests: int) -> int:
            request_validator.callback2(idx, requests)
            return idx + 42 + 2

        @throttle(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=Throttle.MODE_SYNC)
        def f3(*, idx: int) -> int:
            request_validator.callback3(idx=idx)
            return idx + 42 + 3

        @throttle(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=Throttle.MODE_SYNC)
        def f4(*, idx: int, seconds: float) -> int:
            request_validator.callback4(idx=idx, seconds=seconds)
            return idx + 42 + 4

        @throttle(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=Throttle.MODE_SYNC)
        def f5(idx: int, *, interval: float) -> int:
            request_validator.callback5(idx,
                                        interval=interval)
            return idx + 42 + 5

        @throttle(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=Throttle.MODE_SYNC)
        def f6(idx: int, requests: int, *, seconds: float, interval: float
               ) -> int:
            request_validator.callback6(idx,
                                        requests,
                                        seconds=seconds,
                                        interval=interval)
            return idx + 42 + 6

        #######################################################################
        # Invoke the functions
        #######################################################################
        for i in range(requests_arg * request_multiplier):
            rc = f0()
            assert rc == 0
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series

        for i in range(requests_arg * request_multiplier):
            rc = f1(i)
            assert rc == i + 42 + 1
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series

        for i in range(requests_arg * request_multiplier):
            rc = f2(i, requests_arg)
            assert rc == i + 42 + 2
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series

        for i in range(requests_arg * request_multiplier):
            rc = f3(idx=i)
            assert rc == i + 42 + 3
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series

        for i in range(requests_arg * request_multiplier):
            rc = f4(idx=i, seconds=seconds_arg)
            assert rc == i + 42 + 4
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series

        for i in range(requests_arg * request_multiplier):
            rc = f5(idx=i, interval=send_interval_mult_arg)
            assert rc == i + 42 + 5
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series

        for i in range(requests_arg * request_multiplier):
            rc = f6(i, requests_arg,
                    seconds=seconds_arg, interval=send_interval_mult_arg)
            assert rc == i + 42 + 6
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series

    ###########################################################################
    # test_throttle_sync_ec
    ###########################################################################
    def test_pie_throttle_sync_ec(self,
                                  requests_arg: int,
                                  seconds_arg: Union[int, float],
                                  early_count_arg: int,
                                  send_interval_mult_arg: float
                                  ) -> None:
        """Method to start throttle sync_ec tests.

        Args:
            requests_arg: number of requests per interval from fixture
            seconds_arg: interval for number of requests from fixture
            early_count_arg: count used for sync with early count algo
            send_interval_mult_arg: interval between each send of a request
        """
        #######################################################################
        # Instantiate Request Validator
        #######################################################################
        request_multiplier = 32
        send_interval = (seconds_arg / requests_arg) * send_interval_mult_arg
        request_validator = RequestValidator(requests=requests_arg,
                                             seconds=seconds_arg,
                                             mode=Throttle.MODE_SYNC_EC,
                                             early_count=early_count_arg,
                                             lb_threshold=0,
                                             request_mult=request_multiplier,
                                             send_interval=send_interval)

        #######################################################################
        # Decorate functions with throttle
        #######################################################################
        @throttle(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=Throttle.MODE_SYNC_EC,
                  early_count=early_count_arg)
        def f0() -> int:
            request_validator.callback0()
            return 42

        @throttle(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=Throttle.MODE_SYNC_EC,
                  early_count=early_count_arg)
        def f1(idx: int) -> int:
            request_validator.callback1(idx)
            return idx + 42 + 1

        @throttle(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=Throttle.MODE_SYNC_EC,
                  early_count=early_count_arg)
        def f2(idx: int, requests: int) -> int:
            request_validator.callback2(idx, requests)
            return idx + 42 + 2

        @throttle(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=Throttle.MODE_SYNC_EC,
                  early_count=early_count_arg)
        def f3(*, idx: int) -> int:
            request_validator.callback3(idx=idx)
            return idx + 42 + 3

        @throttle(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=Throttle.MODE_SYNC_EC,
                  early_count=early_count_arg)
        def f4(*, idx: int, seconds: float) -> int:
            request_validator.callback4(idx=idx, seconds=seconds)
            return idx + 42 + 4

        @throttle(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=Throttle.MODE_SYNC_EC,
                  early_count=early_count_arg)
        def f5(idx: int, *, interval: float) -> int:
            request_validator.callback5(idx,
                                        interval=interval)
            return idx + 42 + 5

        @throttle(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=Throttle.MODE_SYNC_EC,
                  early_count=early_count_arg)
        def f6(idx: int, requests: int, *, seconds: float, interval: float
               ) -> int:
            request_validator.callback6(idx,
                                        requests,
                                        seconds=seconds,
                                        interval=interval)
            return idx + 42 + 6

        #######################################################################
        # Invoke the functions
        #######################################################################
        for i in range(requests_arg * request_multiplier):
            rc = f0()
            assert rc == 0
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series

        for i in range(requests_arg * request_multiplier):
            rc = f1(i)
            assert rc == i + 42 + 1
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series

        for i in range(requests_arg * request_multiplier):
            rc = f2(i, requests_arg)
            assert rc == i + 42 + 2
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series

        for i in range(requests_arg * request_multiplier):
            rc = f3(idx=i)
            assert rc == i + 42 + 3
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series

        for i in range(requests_arg * request_multiplier):
            rc = f4(idx=i, seconds=seconds_arg)
            assert rc == i + 42 + 4
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series

        for i in range(requests_arg * request_multiplier):
            rc = f5(idx=i, interval=send_interval_mult_arg)
            assert rc == i + 42 + 5
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series

        for i in range(requests_arg * request_multiplier):
            rc = f6(i, requests_arg,
                    seconds=seconds_arg, interval=send_interval_mult_arg)
            assert rc == i + 42 + 6
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series

    ###########################################################################
    # test_throttle_sync_lb
    ###########################################################################
    def test_pie_throttle_sync_lb(self,
                                  requests_arg: int,
                                  seconds_arg: Union[int, float],
                                  lb_threshold_arg: Union[int, float],
                                  send_interval_mult_arg: float
                                  ) -> None:
        """Method to start throttle sync_lb tests.

        Args:
            requests_arg: number of requests per interval from fixture
            seconds_arg: interval for number of requests from fixture
            lb_threshold_arg: threshold used with sync leaky bucket algo
            send_interval_mult_arg: interval between each send of a request
        """
        #######################################################################
        # Instantiate Request Validator
        #######################################################################
        request_multiplier = 32
        send_interval = (seconds_arg / requests_arg) * send_interval_mult_arg
        request_validator = RequestValidator(requests=requests_arg,
                                             seconds=seconds_arg,
                                             mode=Throttle.MODE_SYNC_LB,
                                             early_count=0,
                                             lb_threshold=lb_threshold_arg,
                                             request_mult=request_multiplier,
                                             send_interval=send_interval)

        #######################################################################
        # Decorate functions with throttle
        #######################################################################
        @throttle(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=Throttle.MODE_SYNC_LB,
                  lb_threshold=lb_threshold_arg)
        def f0() -> int:
            request_validator.callback0()
            return 42

        @throttle(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=Throttle.MODE_SYNC_LB,
                  lb_threshold=lb_threshold_arg)
        def f1(idx: int) -> int:
            request_validator.callback1(idx)
            return idx + 42 + 1

        @throttle(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=Throttle.MODE_SYNC_LB,
                  lb_threshold=lb_threshold_arg)
        def f2(idx: int, requests: int) -> int:
            request_validator.callback2(idx, requests)
            return idx + 42 + 2

        @throttle(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=Throttle.MODE_SYNC_LB,
                  lb_threshold=lb_threshold_arg)
        def f3(*, idx: int) -> int:
            request_validator.callback3(idx=idx)
            return idx + 42 + 3

        @throttle(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=Throttle.MODE_SYNC_LB,
                  lb_threshold=lb_threshold_arg)
        def f4(*, idx: int, seconds: float) -> int:
            request_validator.callback4(idx=idx, seconds=seconds)
            return idx + 42 + 4

        @throttle(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=Throttle.MODE_SYNC_LB,
                  lb_threshold=lb_threshold_arg)
        def f5(idx: int, *, interval: float) -> int:
            request_validator.callback5(idx,
                                        interval=interval)
            return idx + 42 + 5

        @throttle(requests=requests_arg,
                  seconds=seconds_arg,
                  mode=Throttle.MODE_SYNC_LB,
                  lb_threshold=lb_threshold_arg)
        def f6(idx: int, requests: int, *, seconds: float, interval: float
               ) -> int:
            request_validator.callback6(idx,
                                        requests,
                                        seconds=seconds,
                                        interval=interval)
            return idx + 42 + 6

        #######################################################################
        # Invoke the functions
        #######################################################################
        for i in range(requests_arg * request_multiplier):
            rc = f0()
            assert rc == 0
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series

        for i in range(requests_arg * request_multiplier):
            rc = f1(i)
            assert rc == i + 42 + 1
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series

        for i in range(requests_arg * request_multiplier):
            rc = f2(i, requests_arg)
            assert rc == i + 42 + 2
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series

        for i in range(requests_arg * request_multiplier):
            rc = f3(idx=i)
            assert rc == i + 42 + 3
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series

        for i in range(requests_arg * request_multiplier):
            rc = f4(idx=i, seconds=seconds_arg)
            assert rc == i + 42 + 4
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series

        for i in range(requests_arg * request_multiplier):
            rc = f5(idx=i, interval=send_interval_mult_arg)
            assert rc == i + 42 + 5
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series

        for i in range(requests_arg * request_multiplier):
            rc = f6(i, requests_arg,
                    seconds=seconds_arg, interval=send_interval_mult_arg)
            assert rc == i + 42 + 6
            time.sleep(send_interval)
        request_validator.validate_series()  # validate for the series

    ###########################################################################
    # test_throttle_shutdown_error
    ###########################################################################
    def test_throttle_shutdown_error(self) -> None:
        """Method to test attempted shutdown in sync mode."""
        #######################################################################
        # call start_shutdown for sync mode
        #######################################################################
        a_throttle1 = Throttle(requests=1,
                               seconds=4,
                               mode=Throttle.MODE_SYNC)

        a_var = [0]

        def f1(a: List[int]) -> None:
            a[0] += 1

        for i in range(4):
            a_throttle1.send_request(f1, a_var)

        with pytest.raises(AttemptedShutdownForSyncThrottle):
            a_throttle1.start_shutdown()

        assert a_var[0] == 4

        # the following requests should not get ignored
        for i in range(6):
            a_throttle1.send_request(f1, a_var)

        # the count should not have changed
        assert a_var[0] == 10

    ###########################################################################
    # test_throttle_shutdown
    ###########################################################################
    def test_throttle_shutdown(self) -> None:
        """Method to test shutdown scenarios."""
        #######################################################################
        # call start_shutdown
        #######################################################################
        b_throttle1 = Throttle(requests=1,
                               seconds=4,
                               mode=Throttle.MODE_ASYNC)

        b_var = [0]

        def f2(b: List[int]) -> None:
            b[0] += 1

        for i in range(32):
            b_throttle1.send_request(f2, b_var)

        time.sleep(14)  # allow 4 requests to be scheduled
        b_throttle1.start_shutdown()

        assert b_var[0] == 4

        # the following requests should get ignored
        for i in range(32):
            b_throttle1.send_request(f2, b_var)

        # the count should not have changed
        assert b_var[0] == 4

    ###########################################################################
    # test_pie_throttle_shutdown
    ###########################################################################
    def test_pie_throttle_shutdown(self) -> None:
        """Test shutdown processing."""
        #######################################################################
        # test 3 - shutdown events with pie throttle
        #######################################################################
        # start_shutdown = threading.Event()
        # shutdown_complete = threading.Event()
        c_var = [0]

        @throttle(requests=1,
                  seconds=4,
                  mode=Throttle.MODE_ASYNC)
        def f3(c: List[int]) -> None:
            c[0] += 1

        for i in range(32):
            f3(c_var)

        time.sleep(14)  # allow 4 requests to be scheduled

        f3.throttle.start_shutdown()
        # start_shutdown.set()
        # shutdown_complete.wait()

        assert c_var[0] == 4

        # the following requests should get ignored
        for i in range(32):
            f3(c_var)

        # the count should not have changed
        assert c_var[0] == 4


###############################################################################
# RequestValidator class
###############################################################################
class RequestValidator:
    """Class to validate the requests."""
    def __init__(self,
                 requests: int,
                 seconds: float,
                 mode: int,
                 early_count: int,
                 lb_threshold: float,
                 request_mult: int,
                 send_interval: float) -> None:
        """Initialize the RequestValidator object.

        Args:
            requests: number of requests per second
            seconds: number of seconds for number of requests
            mode: specifies whether async, sync, sync_ec, or sync_lb
            early_count: the early count for the throttle
            lb_threshold: the leaky bucket threshold
            request_mult: specifies how many requests to make for the test
            send_interval: the interval between sends

        """
        self.requests = requests
        self.seconds = seconds
        self.mode = mode
        self.early_count = early_count
        self.lb_threshold = lb_threshold
        self.request_mult = request_mult
        self.send_interval = send_interval
        self.idx = -1
        self.req_times: List[Tuple[int, float]] = []
        self.normalized_times: List[float] = []
        self.normalized_intervals: List[float] = []
        self.mean_interval = 0.0
        # calculate parms

        self.total_requests = requests * request_mult
        print('total requests:', self.total_requests)
        self.target_interval = seconds / requests

        self.max_interval = max(self.target_interval,
                                self.send_interval)

        print('self.max_interval:', self.max_interval)
        self.min_interval = min(self.target_interval,
                                self.send_interval)

        self.exp_total_time = self.max_interval * self.total_requests
        print('self.exp_total_time:', self.exp_total_time)

        self.target_interval_1pct = self.target_interval * 0.01
        self.target_interval_5pct = self.target_interval * 0.05
        self.target_interval_10pct = self.target_interval * 0.10
        self.target_interval_15pct = self.target_interval * 0.15

        self.max_interval_1pct = self.max_interval * 0.01
        self.max_interval_5pct = self.max_interval * 0.05
        self.max_interval_10pct = self.max_interval * 0.10
        self.max_interval_15pct = self.max_interval * 0.15

        self.min_interval_1pct = self.min_interval * 0.01
        self.min_interval_5pct = self.min_interval * 0.05
        self.min_interval_10pct = self.min_interval * 0.10
        self.min_interval_15pct = self.min_interval * 0.15

        self.reset()

    def reset(self) -> None:
        """Reset the variables to starting values."""
        self.idx = -1
        self.req_times = []
        self.normalized_times = []
        self.normalized_intervals = []
        self.mean_interval = 0.0

    def validate_series(self) -> None:
        """Validate the requests.

        Raises:
            InvalidModeNum: Mode must be 1, 2, 3, or 4

        """
        self.sleep_time = 0
        # if self.mode == Throttle.MODE_ASYNC:
        #     assert len(self.req_times) == self.total_requests
        #     while True:
        #         print('len(self.req_times):', len(self.req_times))
        #         if len(self.req_times) == self.total_requests:
        #             break
        #         time.sleep(1)
        #         self.sleep_time += 1
        #         # diag_msg('len(self.req_times)', len(self.req_times),
        #         #          'self.total_requests', self.total_requests,
        #         #          'sleep_time:', sleep_time)
        #         assert self.sleep_time <= math.ceil(self.exp_total_time) + 5

        assert len(self.req_times) == self.total_requests
        base_time = self.req_times[0][1]
        prev_time = base_time
        for idx, req_item in enumerate(self.req_times):
            assert idx == req_item[0]
            cur_time = req_item[1]
            self.normalized_times.append(cur_time - base_time)
            self.normalized_intervals.append(cur_time - prev_time)
            prev_time = cur_time

        self.mean_interval = self.normalized_times[-1]/(self.total_requests-1)

        if ((self.mode == Throttle.MODE_ASYNC) or
                (self.mode == Throttle.MODE_SYNC) or
                (self.target_interval <= self.send_interval)):
            self.validate_async_sync()
        elif self.mode == Throttle.MODE_SYNC_EC:
            self.validate_sync_ec()
        elif self.mode == Throttle.MODE_SYNC_LB:
            self.validate_sync_lb()
        else:
            raise InvalidModeNum('Mode must be 1, 2, 3, or 4')

        self.reset()

    def validate_async_sync(self) -> None:
        """Validate results for sync."""
        num_early = 0
        num_early_1pct = 0
        num_early_5pct = 0
        num_early_10pct = 0
        num_early_15pct = 0

        num_late = 0
        num_late_1pct = 0
        num_late_5pct = 0
        num_late_10pct = 0
        num_late_15pct = 0

        for interval in self.normalized_intervals[1:]:
            if interval < self.target_interval:
                num_early += 1
            if interval < self.target_interval - self.target_interval_1pct:
                num_early_1pct += 1
            if interval < self.target_interval - self.target_interval_5pct:
                num_early_5pct += 1
            if interval < self.target_interval - self.target_interval_10pct:
                num_early_10pct += 1
            if interval < self.target_interval - self.target_interval_15pct:
                num_early_15pct += 1

            if self.max_interval < interval:
                num_late += 1
            if self.max_interval + self.max_interval_1pct < interval:
                num_late_1pct += 1
            if self.max_interval + self.max_interval_5pct < interval:
                num_late_5pct += 1
            if self.max_interval + self.max_interval_10pct < interval:
                num_late_10pct += 1
            if self.max_interval + self.max_interval_15pct < interval:
                num_late_15pct += 1

        print('num_requests_sent1:', self.total_requests)
        print('num_early1:', num_early)
        print('num_early_1pct1:', num_early_1pct)
        print('num_early_5pct1:', num_early_5pct)
        print('num_early_10pct1:', num_early_10pct)
        print('num_early_15pct1:', num_early_15pct)

        print('num_late1:', num_late)
        print('num_late_1pct1:', num_late_1pct)
        print('num_late_5pct1:', num_late_5pct)
        print('num_late_10pct1:', num_late_10pct)
        print('num_late_15pct1:', num_late_15pct)

        # assert num_early_10pct == 0
        # assert num_early_5pct == 0
        # assert num_early_1pct == 0

        if self.target_interval < self.send_interval:
            assert num_early == 0

        # assert num_late_15pct == 0
        # assert num_late_5pct == 0
        # assert num_late_1pct == 0
        # assert num_late == 0

        self.exp_total_time = self.max_interval * self.total_requests
        print('self.exp_total_time:', self.exp_total_time)
        extra_exp_total_time = self.mean_interval * self.total_requests
        print('extra_exp_total_time:', extra_exp_total_time)
        mean_late_pct = ((self.mean_interval - self.max_interval) /
                         self.max_interval) * 100
        print(f'mean_late_pct: {mean_late_pct:.2f}%')

        extra_time_pct = ((extra_exp_total_time - self.exp_total_time) /
                          self.exp_total_time) * 100

        print(f'extra_time_pct: {extra_time_pct:.2f}%')

        num_to_add = extra_exp_total_time - self.exp_total_time
        print(f'num_to_add: {num_to_add:.2f}')

        print(f'sleep_time: {self.sleep_time}')

        print('self.max_interval:', self.max_interval)
        print('self.mean_interval:', self.mean_interval)
        assert self.max_interval <= self.mean_interval

    def validate_sync_ec(self) -> None:
        """Validate results for sync early count."""
        num_short_early = 0
        num_short_early_1pct = 0
        num_short_early_5pct = 0
        num_short_early_10pct = 0

        num_short_late = 0
        num_short_late_1pct = 0
        num_short_late_5pct = 0
        num_short_late_10pct = 0

        num_long_early = 0
        num_long_early_1pct = 0
        num_long_early_5pct = 0
        num_long_early_10pct = 0

        num_long_late = 0
        num_long_late_1pct = 0
        num_long_late_5pct = 0
        num_long_late_10pct = 0

        long_interval = (((self.early_count + 1) * self.target_interval)
                         - (self.early_count * self.min_interval))

        for idx, interval in enumerate(self.normalized_intervals[1:], 1):
            if idx % (self.early_count + 1):  # if long interval expected
                if interval < long_interval:
                    num_long_early += 1
                if interval < long_interval - self.target_interval_1pct:
                    num_long_early_1pct += 1
                if interval < long_interval - self.target_interval_5pct:
                    num_long_early_5pct += 1
                if interval < (long_interval - self.target_interval_10pct):
                    num_long_early_10pct += 1

                if self.max_interval < interval:
                    num_long_late += 1
                if self.max_interval + self.max_interval_1pct < interval:
                    num_long_late_1pct += 1
                if self.max_interval + self.max_interval_5pct < interval:
                    num_long_late_5pct += 1
                if self.max_interval + self.max_interval_10pct < interval:
                    num_long_late_10pct += 1
            else:
                if interval < self.min_interval:
                    num_short_early += 1
                if interval < self.min_interval - self.min_interval_1pct:
                    num_short_early_1pct += 1
                if interval < self.min_interval - self.min_interval_5pct:
                    num_short_early_5pct += 1
                if interval < (self.min_interval - self.min_interval_10pct):
                    num_short_early_10pct += 1

                if self.min_interval < interval:
                    num_short_late += 1
                if self.min_interval + self.min_interval_1pct < interval:
                    num_short_late_1pct += 1
                if self.min_interval + self.min_interval_5pct < interval:
                    num_short_late_5pct += 1
                if self.min_interval + self.min_interval_10pct < interval:
                    num_short_late_10pct += 1

        print('num_requests_sent2:', self.total_requests)
        print('num_early2:', num_long_early)
        print('num_early_1pct2:', num_long_early_1pct)
        print('num_early_5pct2:', num_long_early_5pct)
        print('num_early_10pct2:', num_long_early_10pct)

        print('num_late2:', num_long_late)
        print('num_late_1pct2:', num_long_late_1pct)
        print('num_late_5pct2:', num_long_late_5pct)
        print('num_late_10pct2:', num_long_late_10pct)

        print('num_early2:', num_short_early)
        print('num_early_1pct2:', num_short_early_1pct)
        print('num_early_5pct2:', num_short_early_5pct)
        print('num_early_10pct2:', num_short_early_10pct)

        print('num_late2:', num_short_late)
        print('num_late_1pct2:', num_short_late_1pct)
        print('num_late_5pct2:', num_short_late_5pct)
        print('num_late_10pct2:', num_short_late_10pct)

        assert num_long_early_10pct == 0
        # assert num_long_early_5pct == 0
        # assert num_long_early_5pct == 0
        # assert num_long_early == 0

        assert num_long_late_10pct == 0
        # assert num_long_late_5pct == 0
        # assert num_long_late_1pct == 0
        # assert num_long_late == 0

        assert num_short_early_10pct == 0
        # assert num_short_early_5pct == 0
        # assert num_short_early_5pct == 0
        # assert num_short_early == 0

        assert num_short_late_10pct == 0
        # assert num_short_late_5pct == 0
        # assert num_short_late_1pct == 0
        # assert num_short_late == 0

        assert self.target_interval <= self.mean_interval

    def validate_sync_lb(self) -> None:
        """Validate the results for sync leaky bucket."""
        amt_added_per_send = self.target_interval - self.send_interval
        num_sends_before_trigger = (math.floor(self.lb_threshold /
                                               amt_added_per_send))
        amt_remaining_in_bucket = (self.lb_threshold
                                   - (num_sends_before_trigger
                                      * self.send_interval))
        amt_over = self.send_interval - amt_remaining_in_bucket

        trigger_interval = self.send_interval + amt_over
        trigger_interval_1pct = trigger_interval * 0.01
        trigger_interval_5pct = trigger_interval * 0.05
        trigger_interval_10pct = trigger_interval * 0.10

        num_short_early = 0
        num_short_early_1pct = 0
        num_short_early_5pct = 0
        num_short_early_10pct = 0

        num_short_late = 0
        num_short_late_1pct = 0
        num_short_late_5pct = 0
        num_short_late_10pct = 0

        num_trigger_early = 0
        num_trigger_early_1pct = 0
        num_trigger_early_5pct = 0
        num_trigger_early_10pct = 0

        num_trigger_late = 0
        num_trigger_late_1pct = 0
        num_trigger_late_5pct = 0
        num_trigger_late_10pct = 0

        num_early = 0
        num_early_1pct = 0
        num_early_5pct = 0
        num_early_10pct = 0

        num_late = 0
        num_late_1pct = 0
        num_late_5pct = 0
        num_late_10pct = 0

        # the following assert ensures our request_multiplier is sufficient
        # to get the bucket filled and then some
        assert (num_sends_before_trigger+8) < len(self.normalized_intervals)

        for idx, interval in enumerate(self.normalized_intervals[1:], 1):
            if idx <= num_sends_before_trigger:
                if interval < self.min_interval:
                    num_short_early += 1
                if interval < self.min_interval - self.min_interval_1pct:
                    num_short_early_1pct += 1
                if interval < self.min_interval - self.min_interval_5pct:
                    num_short_early_5pct += 1
                if interval < (self.min_interval - self.min_interval_10pct):
                    num_short_early_10pct += 1

                if self.min_interval < interval:
                    num_short_late += 1
                if self.min_interval + self.min_interval_1pct < interval:
                    num_short_late_1pct += 1
                if self.min_interval + self.min_interval_5pct < interval:
                    num_short_late_5pct += 1
                if self.min_interval + self.min_interval_10pct < interval:
                    num_short_late_10pct += 1
            elif idx == num_sends_before_trigger + 1:
                if interval < trigger_interval:
                    num_trigger_early += 1
                if interval < trigger_interval - trigger_interval_1pct:
                    num_trigger_early_1pct += 1
                if interval < trigger_interval - trigger_interval_5pct:
                    num_trigger_early_5pct += 1
                if interval < trigger_interval - trigger_interval_10pct:
                    num_trigger_early_10pct += 1

                if trigger_interval < interval:
                    num_trigger_late += 1
                if trigger_interval + trigger_interval_1pct < interval:
                    num_trigger_late_1pct += 1
                if trigger_interval + trigger_interval_5pct < interval:
                    num_trigger_late_5pct += 1
                if trigger_interval + trigger_interval_10pct < interval:
                    num_trigger_late_10pct += 1
            else:
                if interval < self.target_interval:
                    num_early += 1
                if interval < self.target_interval - self.target_interval_1pct:
                    num_early_1pct += 1
                if interval < self.target_interval - self.target_interval_5pct:
                    num_early_5pct += 1
                if interval < self.target_interval - \
                        self.target_interval_10pct:
                    num_early_10pct += 1

                if self.max_interval < interval:
                    num_late += 1
                if self.max_interval + self.max_interval_1pct < interval:
                    num_late_1pct += 1
                if self.max_interval + self.max_interval_5pct < interval:
                    num_late_5pct += 1
                if self.max_interval + self.max_interval_10pct < interval:
                    num_late_10pct += 1

        print('num_requests_sent3:', self.total_requests)

        print('num_short_early3:', num_short_early)
        print('num_short_early_1pct3:', num_short_early_1pct)
        print('num_short_early_5pct3:', num_short_early_5pct)
        print('num_short_early_10pct3:', num_short_early_10pct)

        print('num_short_late3:', num_short_late)
        print('num_short_late_1pct3:', num_short_late_1pct)
        print('num_short_late_5pct3:', num_short_late_5pct)
        print('num_short_late_10pct3:', num_short_late_10pct)

        print('num_trigger_early3:', num_trigger_early)
        print('num_trigger_early_1pct3:', num_trigger_early_1pct)
        print('num_trigger_early_5pct3:', num_trigger_early_5pct)
        print('num_trigger_early_10pct3:', num_trigger_early_10pct)

        print('num_trigger_late3:', num_trigger_late)
        print('num_trigger_late_1pct3:', num_trigger_late_1pct)
        print('num_trigger_late_5pct3:', num_trigger_late_5pct)
        print('num_trigger_late_10pct3:', num_trigger_late_10pct)

        print('num_early3:', num_early)
        print('num_early_1pct3:', num_early_1pct)
        print('num_early_5pct3:', num_early_5pct)
        print('num_early_10pct3:', num_early_10pct)

        print('num_late3:', num_late)
        print('num_late_1pct3:', num_late_1pct)
        print('num_late_5pct3:', num_late_5pct)
        print('num_late_10pct3:', num_late_10pct)

        assert num_short_early_10pct == 0
        assert num_short_late_10pct == 0

        assert num_trigger_early_10pct == 0
        assert num_trigger_late_10pct == 0

        assert num_early_10pct == 0
        assert num_late_10pct == 0

        exp_mean_interval = ((self.send_interval * num_sends_before_trigger)
                             + trigger_interval
                             + (self.target_interval
                                * (self.total_requests
                                   - (num_sends_before_trigger + 1)))
                             ) / (self.total_requests - 1)

        assert exp_mean_interval <= self.mean_interval

    def request0(self) -> int:
        """Request0 target.

        Returns:
            the index reflected back
        """
        self.idx += 1
        self.req_times.append((self.idx, time.time()))
        return self.idx

    def request1(self, idx: int) -> int:
        """Request1 target.

        Args:
            idx: the index of the call

        Returns:
            the index reflected back
        """
        self.req_times.append((idx, time.time()))
        assert idx == self.idx + 1
        self.idx = idx
        return idx

    def request2(self, idx: int, requests: int) -> int:
        """Request2 target.

        Args:
            idx: the index of the call
            requests: number of requests for the throttle

        Returns:
            the index reflected back
        """
        self.req_times.append((idx, time.time()))
        assert idx == self.idx + 1
        assert requests == self.requests
        self.idx = idx
        return idx

    def request3(self, *, idx: int) -> int:
        """Request3 target.

        Args:
            idx: the index of the call

        Returns:
            the index reflected back
        """
        self.req_times.append((idx, time.time()))
        assert idx == self.idx + 1
        self.idx = idx
        return idx

    def request4(self, *, idx: int, seconds: int) -> int:
        """Request4 target.

        Args:
            idx: the index of the call
            seconds: number of seconds for the throttle

        Returns:
            the index reflected back
        """
        self.req_times.append((idx, time.time()))
        assert idx == self.idx + 1
        assert seconds == self.seconds
        self.idx = idx
        return idx

    def request5(self, idx: int, *, interval: float) -> int:
        """Request5 target.

        Args:
            idx: the index of the call
            interval: the interval used between requests

        Returns:
            the index reflected back
        """
        self.req_times.append((idx, time.time()))
        assert idx == self.idx + 1
        assert interval == self.send_interval
        self.idx = idx
        return idx

    def request6(self,
                 idx: int,
                 requests: int,
                 *,
                 seconds: int,
                 interval: float) -> int:
        """Request5 target.

         Args:
            idx: the index of the call
            requests: number of requests for the throttle
            seconds: number of seconds for the throttle
            interval: the interval used between requests

        Returns:
            the index reflected back
        """
        self.req_times.append((idx, time.time()))
        assert idx == self.idx + 1
        assert requests == self.requests
        assert seconds == self.seconds
        assert interval == self.send_interval
        self.idx = idx
        return idx

    ###########################################################################
    # Queue callback targets
    ###########################################################################
    def callback0(self) -> None:
        """Queue the callback for request0."""
        self.idx += 1
        self.req_times.append((self.idx, time.time()))

    def callback1(self, idx: int) -> None:
        """Queue the callback for request0.

        Args:
            idx: index of the request call
        """
        self.req_times.append((idx, time.time()))
        assert idx == self.idx + 1
        self.idx = idx

    def callback2(self, idx: int, requests: int) -> None:
        """Queue the callback for request0.

        Args:
            idx: index of the request call
            requests: number of requests for the throttle
        """
        self.req_times.append((idx, time.time()))
        assert idx == self.idx + 1
        assert requests == self.requests
        self.idx = idx

    def callback3(self, *, idx: int) -> None:
        """Queue the callback for request0.

        Args:
            idx: index of the request call
        """
        self.req_times.append((idx, time.time()))
        assert idx == self.idx + 1
        self.idx = idx

    def callback4(self, *, idx: int, seconds: float) -> None:
        """Queue the callback for request0.

        Args:
            idx: index of the request call
            seconds: number of seconds for the throttle
        """
        self.req_times.append((idx, time.time()))
        assert idx == self.idx + 1
        assert seconds == self.seconds
        self.idx = idx

    def callback5(self,
                  idx: int,
                  *,
                  interval: float) -> None:
        """Queue the callback for request0.

        Args:
            idx: index of the request call
            interval: interval between requests
        """
        self.req_times.append((idx, time.time()))
        assert idx == self.idx + 1
        assert interval == self.send_interval
        self.idx = idx

    def callback6(self,
                  idx: int,
                  requests: int,
                  *,
                  seconds: float,
                  interval: float) -> None:
        """Queue the callback for request0.

        Args:
            idx: index of the request call
            requests: number of requests for the throttle
            seconds: number of seconds for the throttle
            interval: interval between requests
        """
        self.req_times.append((idx, time.time()))
        assert idx == self.idx + 1
        assert requests == self.requests
        assert seconds == self.seconds
        assert interval == self.send_interval
        self.idx = idx


###############################################################################
# TestThrottleDocstrings class
###############################################################################
class TestThrottleDocstrings:
    """Class TestThrottleDocstrings."""
    def test_throttle_with_example_1(self) -> None:
        """Method test_throttle_with_example_1."""
        flowers('Example for README:')

        import time
        from scottbrian_utils.throttle import throttle

        @throttle(requests=3, seconds=1, mode=Throttle.MODE_SYNC)
        def make_request(idx: int, previous_arrival_time: float) -> float:
            arrival_time = time.time()
            if idx == 0:
                previous_arrival_time = arrival_time
            interval = arrival_time - previous_arrival_time
            print(f'request {idx} interval from previous: {interval:0.2f} '
                  f'seconds')
            return arrival_time

        previous_time = 0
        for i in range(10):
            previous_time = make_request(i, previous_time)

    # def test_throttle_with_example_2(self) -> None:
    #     """Method test_throttle_with_example_2."""
    #     print()
    #     print('#' * 50)
    #     print('Example for throttle decorator:')
    #     print()
    #
    #     @throttle(file=sys.stdout)
    #     def func2() -> None:
    #         print('2 * 3 =', 2*3)
    #
    #     func2()
    #
    # def test_throttle_with_example_3(self) -> None:
    #     """Method test_throttle_with_example_3."""
    #     print()
    #     print('#' * 50)
    #     print('Example of printing to stderr:')
    #     print()
    #
    #     @throttle(file=sys.stderr)
    #     def func3() -> None:
    #         print('this text printed to stdout, not stderr')
    #
    #     func3()
    #
    # def test_throttle_with_example_4(self) -> None:
    #     """Method test_throttle_with_example_4."""
    #     print()
    #     print('#' * 50)
    #     print('Example of statically wrapping function with throttle:')
    #     print()
    #
    #     _tbe = False
    #
    #     @throttle(throttle_enabled=_tbe, file=sys.stdout)
    #     def func4a() -> None:
    #         print('this is sample text for _tbe = False static example')
    #
    #     func4a()  # func4a is not wrapped by time box
    #
    #     _tbe = True
    #
    #     @throttle(throttle_enabled=_tbe, file=sys.stdout)
    #     def func4b() -> None:
    #         print('this is sample text for _tbe = True static example')
    #
    #     func4b()  # func4b is wrapped by time box
    #
    # def test_throttle_with_example_5(self) -> None:
    #     """Method test_throttle_with_example_5."""
    #     print()
    #     print('#' * 50)
    #     print('Example of dynamically wrapping function with throttle:')
    #     print()
    #
    #     _tbe = True
    #     def tbe() -> bool: return _tbe
    #
    #     @throttle(throttle_enabled=tbe, file=sys.stdout)
    #     def func5() -> None:
    #         print('this is sample text for the tbe dynamic example')
    #
    #     func5()  # func5 is wrapped by time box
    #
    #     _tbe = False
    #     func5()  # func5 is not wrapped by throttle
    #
    # def test_throttle_with_example_6(self) -> None:
    #     """Method test_throttle_with_example_6."""
    #     print()
    #     print('#' * 50)
    #     print('Example of using different datetime format:')
    #     print()
    #
    #     a_datetime_format: DT_Format = cast(DT_Format, '%m/%d/%y %H:%M:%S')
    #
    #     @throttle(dt_format=a_datetime_format)
    #     def func6() -> None:
    #         print('this is sample text for the datetime format example')
    #
    #     func6()
