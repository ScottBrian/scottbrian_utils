"""Module test_base.

========+
test_base
========+

This module provides base classes that can be used to build a tests and
verify results.


The test_base module contains:

    1) ConfigCmd class
    2) ConfigVerifyBase class

"""
########################################################################
# Standard Library
########################################################################
from abc import ABC, abstractmethod
from collections import deque, defaultdict
from collections.abc import Iterable
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from itertools import combinations, chain
import queue

import logging

from more_itertools import roundrobin

import random
import re
from sys import _getframe
import time
from typing import (
    Any,
    Callable,
    ClassVar,
    cast,
    Generator,
    NamedTuple,
    Type,
    TypeAlias,
    TypedDict,
    TYPE_CHECKING,
    Optional,
    Union,
)
from typing_extensions import Unpack, NotRequired
import threading

########################################################################
# Third Party
########################################################################
import pytest
from scottbrian_utils.msgs import Msgs
from scottbrian_utils.log_verifier import LogVer
from scottbrian_utils.diag_msg import get_formatted_call_sequence, get_caller_info
from scottbrian_locking import se_lock as sel


########################################################################
# Local
########################################################################
import scottbrian_paratools.smart_thread as st


logger = logging.getLogger(__name__)

log_lock: threading.Lock = threading.Lock()


########################################################################
# Type alias
########################################################################
IntOrFloat: TypeAlias = Union[int, float]

StrOrList: TypeAlias = Union[str, list[str]]
StrOrSet: TypeAlias = Union[str, set[str]]

SetStateKey: TypeAlias = tuple[str, str, st.ThreadState, st.ThreadState]

AddRegKey: TypeAlias = tuple[str, str]

AddPaKey: TypeAlias = tuple[str, st.PairKey]

AddStatusBlockKey: TypeAlias = tuple[str, st.PairKey, str]

RequestKey: TypeAlias = tuple[str, str]

SubProcessKey: TypeAlias = tuple[str, str, str, str, str]

RemRegKey: TypeAlias = tuple[str, str]

AckKey: TypeAlias = tuple[str, str]

AlreadyUnregKey: TypeAlias = tuple[str, str]

UnregJoinSuccessKey: TypeAlias = tuple[str, str]

JoinProgKey: TypeAlias = tuple[int, int]

InitCompKey: TypeAlias = tuple[
    str, st.ThreadCreate, st.ThreadState, "AutoStartDecision"
]

CallRefKey: TypeAlias = str

PendEvents: TypeAlias = dict["PE", Any]

CheckPendArg: TypeAlias = tuple[str, st.PairKey]

CheckZeroCtArg: TypeAlias = tuple[str, str]


########################################################################
# SmartThread test exceptions
########################################################################
class ErrorTstSmartThread(Exception):
    """Base class for exception in this module."""

    pass


class IncorrectActionSpecified(ErrorTstSmartThread):
    """IncorrectActionSpecified exception class."""

    pass


class IncorrectDataDetected(ErrorTstSmartThread):
    """IncorrectDataDetected exception class."""

    pass


class UnexpectedEvent(ErrorTstSmartThread):
    """Unexpected action encountered exception class."""

    pass


class UnrecognizedEvent(ErrorTstSmartThread):
    """Unrecognized event ws detected."""

    pass


class UnrecognizedCmd(ErrorTstSmartThread):
    """UnrecognizedCmd exception class."""

    pass


class InvalidConfigurationDetected(ErrorTstSmartThread):
    """UnrecognizedCmd exception class."""

    pass


class InvalidInputDetected(ErrorTstSmartThread):
    """The input is not correct."""

    pass


class CmdTimedOut(ErrorTstSmartThread):
    """The cmd took to long."""

    pass


class CmdFailed(ErrorTstSmartThread):
    """The cmd failed."""

    pass


class FailedLockVerify(ErrorTstSmartThread):
    """An expected lock position was not found."""

    pass


class FailedDefDelVerify(ErrorTstSmartThread):
    """An expected condition was incorrect."""

    pass


class RemainingPendingEvents(ErrorTstSmartThread):
    """There are remaining pending events."""

    pass


exception_list = [
    IncorrectActionSpecified,
    IncorrectDataDetected,
    UnexpectedEvent,
    UnrecognizedEvent,
    UnrecognizedCmd,
    InvalidInputDetected,
    CmdTimedOut,
    CmdFailed,
    FailedLockVerify,
    FailedDefDelVerify,
    RemainingPendingEvents,
]


RemSbKey: TypeAlias = tuple[str, tuple[str, str], DefDelReasons]

RefPendKey: TypeAlias = tuple[str, st.PairKey]

RemPaeKey: TypeAlias = tuple[str, tuple[str, str]]


########################################################################
# get_ptime
########################################################################
def get_ptime() -> str:
    """Returns a printable UTC time stamp.

    Returns:
        a timestamp as a string
    """
    now_time = datetime.now(UTC)
    print_time = now_time.strftime("%H:%M:%S.%f")

    return print_time


@dataclass
class CheckExpectedResponsesArgs:
    """Parameters for received responses with WaitForCondition."""

    requestors: set[str]
    exp_response_targets: set[str]
    request: st.ReqType


########################################################################
# wait_for
########################################################################
def wait_for(condition: Callable[..., bool], timeout_value: IntOrFloat = 15) -> None:
    """Wait for a condition with timeout.

    Args:
        condition: function to call that returns True when the condition
            is satisfied
        timeout_value: the number of seconds to allow the condition to
            be satisfied before raising a timeout error

    Raises:
        CmdTimedOut: wait_for called from line_num took longer than '
            timeout_value seconds waiting for condition.

    """
    start_time = time.time()
    logging.debug(f"wait_for entered with {condition=}")
    while not condition():
        time.sleep(0.2)
        if time.time() - start_time > timeout_value:
            frame = _getframe(1)
            caller_info = get_caller_info(frame)
            line_num = caller_info.line_num
            del frame
            raise CmdTimedOut(
                f"wait_for called from {line_num=} took longer than "
                f"{timeout_value} seconds waiting for {condition=}."
            )


########################################################################
# LockMgr
########################################################################
class LockMgr:
    """Class LockMsg manages locking for test cases."""

    def __init__(self, config_ver: "ConfigVerifier", locker_names: list[str]):
        """Initialize the object.

        Args:
            config_ver: the ConfigVerifier object
            locker_names: thread names that do the locking
        """
        self.config_ver = config_ver
        self.locker_avail_q: deque[str] = deque(locker_names)
        self.lock_positions: list[str] = []

    ####################################################################
    # get_lock
    ####################################################################
    def get_lock(self, alt_frame_num: int = 1) -> None:
        """Get the lock and verify the lock positions.

        Args:
            alt_frame_num: frame to get line_num

        """
        locker_name = self.locker_avail_q.pop()
        obtain_lock_serial_num = self.config_ver.add_cmd(
            LockObtain(cmd_runners=locker_name), alt_frame_num=alt_frame_num
        )
        self.lock_positions.append(locker_name)

        # we can confirm only this first lock obtain
        if len(self.lock_positions) == 1:
            self.config_ver.add_cmd(
                ConfirmResponse(
                    cmd_runners=[self.config_ver.commander_name],
                    confirm_cmd="LockObtain",
                    confirm_serial_num=obtain_lock_serial_num,
                    confirmers=locker_name,
                ),
                alt_frame_num=alt_frame_num,
            )

        self.config_ver.add_cmd(
            LockVerify(
                cmd_runners=self.config_ver.commander_name,
                exp_positions=self.lock_positions.copy(),
            ),
            alt_frame_num=alt_frame_num,
        )

    ####################################################################
    # start_request
    ####################################################################
    def start_request(
        self, requestor_name: str, trailing_lock: bool = True, alt_frame_num: int = 1
    ) -> None:
        """Append a requestor and verify lock positions.

        Args:
            requestor_name: thread name of requestor that just obtained
                the lock
            trailing_lock: if True, add a lock at end
            alt_frame_num: frame to get line_num
        """
        self.lock_positions.append(requestor_name)
        self.config_ver.add_cmd(
            LockVerify(
                cmd_runners=self.config_ver.commander_name,
                exp_positions=self.lock_positions.copy(),
            ),
            alt_frame_num=alt_frame_num,
        )
        if trailing_lock:
            self.get_lock(alt_frame_num=alt_frame_num + 1)

    ####################################################################
    # drop_lock
    ####################################################################
    def drop_lock(
        self,
        requestor_complete: bool = False,
        free_all: bool = False,
        alt_frame_num: int = 1,
    ) -> None:
        """Drop the lock and verify positions.

        Args:
            requestor_complete: If True, the requestor has completed
                its smart request and can be removed from the positions
                list. If False, request has progressed and should now be
                behind another lock.
            free_all: specifies that all requests will complete
            alt_frame_num: frame to get line_num
        """
        locker_name = self.lock_positions.pop(0)
        self.locker_avail_q.append(locker_name)
        self.config_ver.add_cmd(
            LockRelease(cmd_runners=locker_name), alt_frame_num=alt_frame_num
        )

        requestor_name = self.lock_positions.pop(0)
        if not requestor_complete:
            self.lock_positions.append(requestor_name)
        if free_all:
            self.lock_positions = []

        self.config_ver.add_cmd(
            LockVerify(
                cmd_runners=self.config_ver.commander_name,
                exp_positions=self.lock_positions.copy(),
            ),
            alt_frame_num=alt_frame_num,
        )

    ####################################################################
    # complete_request
    ####################################################################
    def complete_request(self, free_all: bool = False, alt_frame_num: int = 1) -> None:
        """Drop the lock and verify positions.

        Args:
            free_all: specifies that all requests will complete
            alt_frame_num: frame to get line_num
        """
        self.drop_lock(
            requestor_complete=True, free_all=free_all, alt_frame_num=alt_frame_num
        )

    ####################################################################
    # advance_request
    ####################################################################
    def advance_request(
        self, num_times: int = 1, trailing_lock: bool = True, alt_frame_num: int = 1
    ) -> None:
        """Drop the lock, requeue the requestor, verify positions.

        Args:
            num_times: number of times to do the advance
            trailing_lock: if True, add a lock at end
            alt_frame_num: frame to get line_num
        """
        for _ in range(num_times):
            self.drop_lock(requestor_complete=False, alt_frame_num=alt_frame_num + 1)
            if trailing_lock:
                self.get_lock(alt_frame_num=alt_frame_num + 1)

    ####################################################################
    # advance_request
    ####################################################################
    def swap_requestors(self, alt_frame_num: int = 1) -> None:
        """Swap the requests lock positions.

        Args:
            alt_frame_num: frame to get line_num
        """
        lock_pos_1 = self.lock_positions[1]
        self.lock_positions[1] = self.lock_positions[3]
        self.lock_positions[3] = lock_pos_1

        self.config_ver.add_cmd(
            LockSwap(
                cmd_runners=self.config_ver.commander_name,
                new_positions=self.lock_positions.copy(),
            ),
            alt_frame_num=alt_frame_num,
        )
        self.config_ver.add_cmd(
            LockVerify(
                cmd_runners=self.config_ver.commander_name,
                exp_positions=self.lock_positions.copy(),
            ),
            alt_frame_num=alt_frame_num,
        )


########################################################################
# VerifyData items
########################################################################
class VerifyType(Enum):
    """VerifyType used to select the verification to be done."""

    VerifyStructures = auto()
    VerifyAlive = auto()
    VerifyNotAlive = auto()
    VerifyState = auto()
    VerifyInRegistry = auto()
    VerifyNotInRegistry = auto()
    VerifyAliveState = auto()
    VerifyRegisteredState = auto()
    VerifyStoppedState = auto()
    VerifyPaired = auto()
    VerifyNotPaired = auto()
    VerifyHalfPaired = auto()
    VerifyPendingFlags = auto()
    VerifyCounts = auto()


@dataclass
class PendingFlags:
    """PendingFlags used for setting and checking the pending flags."""

    pending_request: bool = False
    pending_msgs: int = 0
    pending_wait: bool = False
    pending_sync: bool = False


@dataclass
class VerifyData:
    """VerifyData used for the verify methods."""

    cmd_runner: str
    verify_type: VerifyType
    names_to_check: set[str]
    aux_names: set[str]
    state_to_check: st.ThreadState
    exp_pending_flags: PendingFlags
    obtain_reg_lock: bool
    num_registered: int = 0
    num_active: int = 0
    num_stopped: int = 0


@dataclass
class RegistrySnapshotItem:
    """RegistrySnapshotItem used to verify registry."""

    is_alive: bool
    state: st.ThreadState


@dataclass
class StatusBlockSnapshotItem:
    """StatusBlockSnapshotItem used for pending flags."""

    del_def_flag: bool = False
    pending_request: bool = False
    pending_msg_count: int = 0
    pending_wait: bool = False
    pending_sync: bool = False


RegistryItems: TypeAlias = dict[str, RegistrySnapshotItem]
StatusBlockItems: TypeAlias = dict[str, StatusBlockSnapshotItem]
PairArrayItems: TypeAlias = dict[st.PairKey, StatusBlockItems]


@dataclass
class SnapShotDataItem:
    """SnapShotData used to collect mock array info."""

    registry_items: RegistryItems
    pair_array_items: PairArrayItems
    verify_data: VerifyData


@contextmanager
def conditional_registry_lock(
    lock: sel.SELock, obtain_tf: bool
) -> Generator[None, None, None]:
    """Obtain the connection_block lock.

    This method is called to conditionally obtain a lock using a with
    statement.

    Args:
        lock: the lock to obtain
        obtain_tf: whether to obtain the lock

    """
    # if request needs the lock
    if obtain_tf:
        lock.obtain_excl()
    try:
        yield
    finally:
        # release the lock if it was obtained
        if obtain_tf:
            lock.release()


########################################################################
# CommanderConfig
########################################################################
class AppConfig(Enum):
    """Commander configuration choices."""

    ScriptStyle = auto()
    F1Rtn = auto()
    CurrentThreadApp = auto()
    RemoteThreadApp = auto()
    RemoteSmartThreadApp = auto()
    RemoteSmartThreadApp2 = auto()


########################################################################
# RequestConfirmParms
########################################################################
@dataclass()
class RequestConfirmParms:
    """Request confirm parms."""

    request_name: str
    serial_number: int


########################################################################
# timeout_type used to specify whether to use timeout on various cmds
########################################################################
class TimeoutType(Enum):
    """Timeout type for test."""

    TimeoutNone = auto()
    TimeoutFalse = auto()
    TimeoutTrue = auto()


########################################################################
# get_names
########################################################################
def get_names(stem: str, count: int) -> set[str]:
    """Create a set of names give stem and count.

    Args:
        stem: base of name to which index will be added
        count: number of names to create

    Returns:
        A set of names

    """
    if count:
        return {stem + str(i) for i in range(count)}
    else:
        return set()


########################################################################
# get_set
########################################################################
def get_set(item: Optional[Iterable[str]] = None) -> set[Any]:
    """Return a set given the iterable input.

    Args:
        item: iterable to be returned as a set

    Returns:
        A set created from the input iterable item. Note that the set
        will be empty if None was passed in.
    """
    return set({item} if isinstance(item, str) else item or "")


########################################################################
# ConfigCmd
########################################################################
class ConfigCmd(ABC):
    """Configuration command base class."""

    def __init__(self, cmd_runners: Iterable[str]) -> None:
        """Initialize the instance.

        Args:
            cmd_runners: thread names that will execute the command

        """
        # The serial number, line_num, and config_ver are filled in
        # by the ConfigVerifier add_cmd method just before queueing
        # the command.
        self.serial_num: int = 0
        self.line_num: int = 0
        self.alt_line_num: int = 0
        self.config_ver: "ConfigVerifier"

        # specified_args are set in each subclass
        self.specified_args: dict[str, Any] = {}

        self.cmd_runners = get_set(cmd_runners)

        self.arg_list: list[str] = ["cmd_runners", "serial_num", "line_num"]

    def __repr__(self) -> str:
        """Method to provide repr."""
        if TYPE_CHECKING:
            __class__: Type[ConfigVerifier]  # noqa: F842
        classname = self.__class__.__name__
        parms = f"serial={self.serial_num}, line={self.line_num}"
        if self.alt_line_num:
            parms += f"({self.alt_line_num})"
        comma = ", "
        for key, item in self.specified_args.items():
            if item:  # if not None
                if key in self.arg_list:
                    if type(item) is str:
                        parms += comma + f"{key}='{item}'"
                    else:
                        parms += comma + f"{key}={item}"
                    # comma = ', '  # after first item, now need comma
            if key == "f1_create_items":
                create_names: list[str] = []
                for create_item in item:
                    create_names.append(create_item.name)
                parms += comma + f"{create_names=}"

        return f"{classname}({parms})"

    @abstractmethod
    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
           cmd_runner: name of thread running the command
        """
        pass


########################################################################
# ConfirmResponse
########################################################################
class ConfirmResponse(ConfigCmd):
    """Confirm that an earlier command has completed."""

    def __init__(
        self,
        cmd_runners: Iterable[str],
        confirm_cmd: str,
        confirm_serial_num: int,
        confirmers: Iterable[str],
    ) -> None:
        """Initialize the instance.

        Args:
            cmd_runners: thread names that will execute the command
            confirm_cmd: command to be confirmed
            confirm_serial_num: serial number of command to confirm
            confirmers: cmd runners of the cmd to be confirmed
        """
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        self.confirm_cmd = confirm_cmd
        self.confirm_serial_num = confirm_serial_num

        self.confirmers = get_set(confirmers)

        self.arg_list += ["confirm_cmd", "confirm_serial_num", "confirmers"]

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
           cmd_runner: name of thread running the command
        """
        start_time = time.time()
        work_confirmers = self.confirmers.copy()
        if not work_confirmers:
            raise InvalidInputDetected(
                "ConfirmResponse detected an empty set of confirmers"
            )
        while work_confirmers:
            for name in work_confirmers:
                # If the serial number is in the completed_cmds for
                # this name then the command was completed. Remove the
                # target_rtn name and break to start looking again with
                # one less target_rtn until no targets remain.
                if self.confirm_serial_num in self.config_ver.completed_cmds[name]:
                    work_confirmers.remove(name)
                    break
            time.sleep(0.2)
            timeout_value = 60
            if time.time() - start_time > timeout_value:
                raise CmdTimedOut(
                    "ConfirmResponse serial_num "
                    f"{self.serial_num} took longer than "
                    f"{timeout_value} seconds waiting "
                    f"for {work_confirmers} to complete "
                    f"cmd {self.confirm_cmd} with "
                    f"serial_num {self.confirm_serial_num}."
                )


########################################################################
# ConfirmResponseNot
########################################################################
class ConfirmResponseNot(ConfirmResponse):
    """Confirm that an earlier command has not yet completed."""

    def __init__(
        self,
        cmd_runners: Iterable[str],
        confirm_cmd: str,
        confirm_serial_num: int,
        confirmers: Iterable[str],
    ) -> None:
        """Initialize the instance.

        Args:
            cmd_runners: thread names that will execute the command
            confirm_cmd: command to be confirmed as not yet completed
            confirm_serial_num: serial number of command to not confirm
            confirmers: cmd runners of the cmd to be not confirmed
        """
        super().__init__(
            cmd_runners=cmd_runners,
            confirm_cmd=confirm_cmd,
            confirm_serial_num=confirm_serial_num,
            confirmers=confirmers,
        )
        self.specified_args = locals()  # used for __repr__

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
           cmd_runner: name of thread running the command
        """
        for name in self.confirmers:
            # If the serial number is in the completed_cmds for
            # this name then the command was completed. Remove the
            # target_rtn name and break to start looking again with one
            # less target_rtn until no targets remain.
            if self.confirm_serial_num in self.config_ver.completed_cmds[name]:
                raise CmdFailed(
                    "ConfirmResponseNot found that "
                    f"{name} completed {self.confirm_cmd=} "
                    f"with {self.serial_num=}."
                )


########################################################################
# CreateF1AutoStart
########################################################################
class CreateF1AutoStart(ConfigCmd):
    """Create an f1 thread with autostart."""

    def __init__(
        self,
        cmd_runners: Iterable[str],
        f1_create_items: list["F1CreateItem"],
    ) -> None:
        """Initialize the instance.

        Args:
            cmd_runners: thread names that will execute the command
            f1_create_items: list of names and attributes to be used
                when creating the threads
        """
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        self.f1_create_items = f1_create_items

        self.args_list = ["f1_create_items"]

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
           cmd_runner: name of thread running the command
        """
        for f1_item in self.f1_create_items:
            self.config_ver.create_f1_thread(
                cmd_runner=cmd_runner,
                name=f1_item.name,
                target=f1_item.target_rtn,
                app_config=f1_item.app_config,
                auto_start=True,
            )


########################################################################
# CreateF1NoStart
########################################################################
class CreateF1NoStart(CreateF1AutoStart):
    """Create an f1 thread with no autostart."""

    def __init__(
        self,
        cmd_runners: Iterable[str],
        f1_create_items: list["F1CreateItem"],
    ) -> None:
        """Initialize the instance.

        Args:
            cmd_runners: thread names that will execute the command
            f1_create_items: list of names and attributes to be used
                when creating the threads
        """
        super().__init__(cmd_runners=cmd_runners, f1_create_items=f1_create_items)
        self.specified_args = locals()  # used for __repr__

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        for f1_item in self.f1_create_items:
            self.config_ver.create_f1_thread(
                cmd_runner=cmd_runner,
                name=f1_item.name,
                target=f1_item.target_rtn,
                app_config=f1_item.app_config,
                auto_start=False,
            )


########################################################################
# ExitThread
########################################################################
class ExitThread(ConfigCmd):
    """Cause thread to exit its command loop."""

    def __init__(self, cmd_runners: Iterable[str], stopped_by: str) -> None:
        """Initialize the instance.

        Args:
            cmd_runners: thread names that will execute the command
            stopped_by: name of thread that did the stop
        """
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        self.stopped_by = stopped_by

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.exit_thread(cmd_runner=cmd_runner, stopped_by=self.stopped_by)


########################################################################
# Join
########################################################################
class Join(ConfigCmd):
    """Do smart_join."""

    def __init__(
        self,
        cmd_runners: Iterable[str],
        join_names: Iterable[str],
        unreg_names: Optional[Iterable[str]] = None,
        log_msg: Optional[str] = None,
    ) -> None:
        """Initialize the instance.

        Args:
            cmd_runners: thread names that will execute the command
            join_names: thread names to join
            unreg_names: thread names that are already unregistered
            log_msg: log message specification for the smart_join
        """
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        self.join_names = get_set(join_names)
        self.unreg_names = get_set(unreg_names)
        self.log_msg = log_msg
        self.arg_list += ["join_names", "unreg_names"]

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.handle_join(
            cmd_runner=cmd_runner,
            join_names=self.join_names,
            unreg_names=self.unreg_names,
            timeout_type=TimeoutType.TimeoutNone,
            timeout=0,
            log_msg=self.log_msg,
        )


########################################################################
# JoinTimeoutFalse
########################################################################
class JoinTimeoutFalse(Join):
    """Do smart_join with timeout false."""

    def __init__(
        self,
        cmd_runners: Iterable[str],
        join_names: Iterable[str],
        timeout: IntOrFloat,
        unreg_names: Optional[Iterable[str]] = None,
        log_msg: Optional[str] = None,
    ) -> None:
        """Initialize the instance.

        Args:
            cmd_runners: thread names that will execute the command
            join_names: thread names to join
            unreg_names: thread names that are already unregistered
            timeout: timeout specification for the smart_join
            log_msg: log message specification for the smart_join
        """
        super().__init__(
            cmd_runners=cmd_runners,
            join_names=join_names,
            unreg_names=unreg_names,
            log_msg=log_msg,
        )
        self.specified_args = locals()  # used for __repr__

        self.timeout = timeout
        self.arg_list += ["timeout"]

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.handle_join(
            cmd_runner=cmd_runner,
            join_names=self.join_names,
            unreg_names=self.unreg_names,
            timeout_type=TimeoutType.TimeoutFalse,
            timeout=self.timeout,
            log_msg=self.log_msg,
        )


########################################################################
# JoinTimeoutTrue
########################################################################
class JoinTimeoutTrue(JoinTimeoutFalse):
    """Do smart_join with timeout true."""

    def __init__(
        self,
        cmd_runners: Iterable[str],
        join_names: Iterable[str],
        timeout: IntOrFloat,
        timeout_names: Iterable[str],
        unreg_names: Optional[Iterable[str]] = None,
        log_msg: Optional[str] = None,
    ) -> None:
        """Initialize the instance.

        Args:
            cmd_runners: thread names that will execute the command
            join_names: thread names to join
            unreg_names: thread names that are already unregistered
            timeout: timeout specification for the smart_join
            timeout_names: thread names expected to cause timeout
            log_msg: log message specification for the smart_join
        """
        super().__init__(
            cmd_runners=cmd_runners,
            join_names=join_names,
            unreg_names=unreg_names,
            timeout=timeout,
            log_msg=log_msg,
        )
        self.specified_args = locals()  # used for __repr__

        self.timeout_names = get_set(timeout_names)
        self.arg_list += ["timeout_names"]

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        if self.timeout_names:
            self.config_ver.handle_join(
                cmd_runner=cmd_runner,
                join_names=self.join_names,
                unreg_names=self.unreg_names,
                timeout_type=TimeoutType.TimeoutTrue,
                timeout=self.timeout,
                timeout_names=self.timeout_names,
                log_msg=self.log_msg,
            )
        else:
            self.config_ver.handle_join(
                cmd_runner=cmd_runner,
                join_names=self.join_names,
                unreg_names=self.unreg_names,
                timeout_type=TimeoutType.TimeoutFalse,
                timeout=self.timeout,
                log_msg=self.log_msg,
            )


########################################################################
# LockObtain
########################################################################
class LockObtain(ConfigCmd):
    """Obtain the registry lock."""

    def __init__(self, cmd_runners: Iterable[str]) -> None:
        """Initialize the instance.

        Args:
            cmd_runners: thread names that will execute the command

        """
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.lock_obtain()


########################################################################
# LockRelease
########################################################################
class LockRelease(ConfigCmd):
    """Release the registry lock."""

    def __init__(self, cmd_runners: Iterable[str]) -> None:
        """Initialize the instance.

        Args:
            cmd_runners: thread names that will execute the command

        """
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.lock_release()


########################################################################
# LockSwap
########################################################################
class LockSwap(ConfigCmd):
    """Swap the lock positions."""

    def __init__(self, cmd_runners: Iterable[str], new_positions: list[str]) -> None:
        """Initialize the instance.

        Args:
            cmd_runners: thread names that will execute the command
            new_positions: list of thread names for new position
        """
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        self.new_positions = new_positions
        self.arg_list += ["new_positions"]

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.lock_swap(
            cmd_runner=cmd_runner, new_positions=self.new_positions
        )


########################################################################
# LockVerify
########################################################################
class LockVerify(ConfigCmd):
    """Verify the registry lock has the expected owners and waiters."""

    def __init__(self, cmd_runners: Iterable[str], exp_positions: list[str]) -> None:
        """Initialize the instance.

        Args:
            cmd_runners: thread names that will execute the command
            exp_positions: thread names for expected positions
        """
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        self.exp_positions = exp_positions
        self.arg_list += ["exp_positions"]

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.lock_verify(
            cmd_runner=cmd_runner,
            exp_positions=self.exp_positions,
            line_num=self.line_num,
        )


########################################################################
# Pause
########################################################################
class Pause(ConfigCmd):
    """Pause the commands."""

    def __init__(self, cmd_runners: Iterable[str], pause_seconds: IntOrFloat) -> None:
        """Initialize the instance.

        Args:
            cmd_runners: thread names that will execute the command
            pause_seconds: number seconds to sleep
        """
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        self.pause_seconds = pause_seconds

        self.arg_list += ["pause_seconds"]

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        time.sleep(self.pause_seconds)


########################################################################
# RecvMsg
########################################################################
class RecvMsg(ConfigCmd):
    """Do smart_recv."""

    def __init__(
        self,
        cmd_runners: Iterable[str],
        senders: Iterable[str],
        exp_senders: Iterable[str],
        exp_msgs: SendRecvMsgs,
        sender_count: Optional[int] = None,
        stopped_remotes: Optional[Iterable[str]] = None,
        deadlock_remotes: Optional[Iterable[str]] = None,
        log_msg: Optional[str] = None,
    ) -> None:
        """Initialize the instance.

        Args:
            cmd_runners: thread names that will execute the command
            senders: thread names that will do smart_send
            exp_senders: names of threads that are expected to send a
                msg depending on the RcvType
            exp_msgs: messages to be sent and verified
            sender_count: specification for smart_recv for how many
                senders are needed to satisfy the smart_recv
            stopped_remotes: thread names that are stopped
            deadlock_remotes: thread names that cause deadlock
            log_msg: log message to specify on the smart_recv
        """
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        self.senders = get_set(senders)

        self.exp_senders = get_set(exp_senders)

        self.exp_msgs = exp_msgs

        self.sender_count = sender_count

        self.log_msg = log_msg

        self.stopped_remotes = get_set(stopped_remotes)

        self.deadlock_remotes = get_set(deadlock_remotes)

        self.arg_list += [
            "senders",
            "exp_senders",
            "sender_count",
            "stopped_remotes",
            "deadlock_remotes",
        ]

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.handle_recv_msg(
            cmd_runner=cmd_runner,
            senders=self.senders,
            exp_senders=self.exp_senders,
            exp_msgs=self.exp_msgs,
            sender_count=self.sender_count,
            stopped_remotes=self.stopped_remotes,
            deadlock_remotes=self.deadlock_remotes,
            deadlock_or_timeout=False,
            timeout_type=TimeoutType.TimeoutNone,
            timeout=0,
            timeout_names=set(),
            log_msg=self.log_msg,
        )


########################################################################
# RecvMsgTimeoutFalse
########################################################################
class RecvMsgTimeoutFalse(RecvMsg):
    """Do smart_recv with timeout false."""

    def __init__(
        self,
        cmd_runners: Iterable[str],
        senders: Iterable[str],
        exp_senders: Iterable[str],
        exp_msgs: SendRecvMsgs,
        timeout: IntOrFloat,
        sender_count: Optional[int] = None,
        stopped_remotes: Optional[Iterable[str]] = None,
        deadlock_remotes: Optional[Iterable[str]] = None,
        log_msg: Optional[str] = None,
    ) -> None:
        """Initialize the instance.

        Args:
            cmd_runners: thread names that will execute the command
            senders: thread names that will do smart_send
            exp_senders: names of threads that are expected to send a
                msg depending on the RcvType
            exp_msgs: messages to be sent and verified
            timeout: value to specify on the smart_recv
            sender_count: specification for smart_recv for how many
                senders are needed to satisfy the smart_recv
            stopped_remotes: thread names that are stopped
            deadlock_remotes: thread names that cause deadlock
            log_msg: log message to specify on the smart_recv
        """
        super().__init__(
            cmd_runners=cmd_runners,
            senders=senders,
            exp_senders=exp_senders,
            exp_msgs=exp_msgs,
            sender_count=sender_count,
            stopped_remotes=stopped_remotes,
            deadlock_remotes=deadlock_remotes,
            log_msg=log_msg,
        )
        self.specified_args = locals()  # used for __repr__

        self.timeout = timeout

        self.arg_list += ["timeout"]

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.handle_recv_msg(
            cmd_runner=cmd_runner,
            senders=self.senders,
            exp_senders=self.exp_senders,
            exp_msgs=self.exp_msgs,
            sender_count=self.sender_count,
            stopped_remotes=self.stopped_remotes,
            deadlock_remotes=self.deadlock_remotes,
            deadlock_or_timeout=False,
            timeout_type=TimeoutType.TimeoutFalse,
            timeout=self.timeout,
            timeout_names=set(),
            log_msg=self.log_msg,
        )


########################################################################
# RecvMsgTimeoutTrue
########################################################################
class RecvMsgTimeoutTrue(RecvMsgTimeoutFalse):
    """Do smart_recv with timeout true."""

    def __init__(
        self,
        cmd_runners: Iterable[str],
        senders: Iterable[str],
        exp_senders: Iterable[str],
        exp_msgs: SendRecvMsgs,
        timeout: IntOrFloat,
        timeout_names: Iterable[str],
        sender_count: Optional[int] = None,
        stopped_remotes: Optional[Iterable[str]] = None,
        deadlock_remotes: Optional[Iterable[str]] = None,
        deadlock_or_timeout: bool = False,
        log_msg: Optional[str] = None,
    ) -> None:
        """Initialize the instance.

        Args:
            cmd_runners: thread names that will execute the command
            senders: thread names that will do smart_send
            exp_senders: names of threads that are expected to send a
                msg depending on the RcvType
            exp_msgs: messages to be sent and verified
            timeout: value to specify on the smart_recv
            timeout_names: thread names that are expected to cause a
                timeout
            sender_count: specification for smart_recv for how many
                senders are needed to satisfy the smart_recv
            stopped_remotes: thread names that are stopped
            deadlock_remotes: thread names that cause deadlock
            deadlock_or_timeout: except deadlock or timeout
            log_msg: log message to specify on the smart_recv
        """
        super().__init__(
            cmd_runners=cmd_runners,
            senders=senders,
            exp_senders=exp_senders,
            exp_msgs=exp_msgs,
            timeout=timeout,
            sender_count=sender_count,
            stopped_remotes=stopped_remotes,
            deadlock_remotes=deadlock_remotes,
            log_msg=log_msg,
        )
        self.specified_args = locals()  # used for __repr__

        self.timeout_names = get_set(timeout_names)

        self.deadlock_or_timeout = deadlock_or_timeout

        self.arg_list += ["timeout_names"]

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.handle_recv_msg(
            cmd_runner=cmd_runner,
            senders=self.senders,
            exp_senders=self.exp_senders,
            exp_msgs=self.exp_msgs,
            sender_count=self.sender_count,
            stopped_remotes=self.stopped_remotes,
            deadlock_remotes=self.deadlock_remotes,
            deadlock_or_timeout=self.deadlock_or_timeout,
            timeout_type=TimeoutType.TimeoutTrue,
            timeout=self.timeout,
            timeout_names=self.timeout_names,
            log_msg=self.log_msg,
        )


########################################################################
# Resume
########################################################################
class Resume(ConfigCmd):
    """Do smart_resume."""

    def __init__(
        self,
        cmd_runners: Iterable[str],
        targets: Iterable[str],
        exp_resumed_targets: Iterable[str],
        stopped_remotes: Optional[Iterable[str]] = None,
        log_msg: Optional[str] = None,
    ) -> None:
        """Initialize the instance.

        Args:
            cmd_runners: thread names that will execute the command
            targets: thread names to resume
            exp_resumed_targets: thread names expected to be resumed
            stopped_remotes: thread names that are stopped
            log_msg: log msg for smart_resume
        """
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        self.targets = get_set(targets)

        self.exp_resumed_targets = get_set(exp_resumed_targets)

        self.stopped_remotes = get_set(stopped_remotes)

        self.log_msg = log_msg

        self.arg_list += ["targets", "exp_resumed_targets", "stopped_remotes"]

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.handle_resume(
            cmd_runner=cmd_runner,
            targets=self.targets,
            exp_resumed_targets=self.exp_resumed_targets,
            stopped_remotes=self.stopped_remotes,
            timeout=0,
            timeout_names=set(),
            timeout_type=TimeoutType.TimeoutNone,
            log_msg=self.log_msg,
        )


########################################################################
# ResumeTimeoutFalse
########################################################################
class ResumeTimeoutFalse(Resume):
    """Do smart_resume with timeout false."""

    def __init__(
        self,
        cmd_runners: Iterable[str],
        targets: Iterable[str],
        exp_resumed_targets: Iterable[str],
        timeout: IntOrFloat,
        stopped_remotes: Optional[Iterable[str]] = None,
        log_msg: Optional[str] = None,
    ) -> None:
        """Initialize the instance.

        Args:
            cmd_runners: thread names that will execute the command
            targets: thread names to resume
            exp_resumed_targets: thread names expected to be resumed
            stopped_remotes: thread names that are stopped
            timeout: value for smart_resume
            log_msg: log msg for smart_resume
        """
        super().__init__(
            cmd_runners=cmd_runners,
            targets=targets,
            exp_resumed_targets=exp_resumed_targets,
            stopped_remotes=stopped_remotes,
            log_msg=log_msg,
        )
        self.specified_args = locals()  # used for __repr__

        self.timeout = timeout

        self.arg_list += ["timeout"]

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.handle_resume(
            cmd_runner=cmd_runner,
            targets=self.targets,
            exp_resumed_targets=self.exp_resumed_targets,
            stopped_remotes=self.stopped_remotes,
            timeout=self.timeout,
            timeout_names=set(),
            timeout_type=TimeoutType.TimeoutFalse,
            log_msg=self.log_msg,
        )


########################################################################
# ResumeTimeoutFalse
########################################################################
class ResumeTimeoutTrue(ResumeTimeoutFalse):
    """Do smart_resume with timeout true."""

    def __init__(
        self,
        cmd_runners: Iterable[str],
        targets: Iterable[str],
        exp_resumed_targets: Iterable[str],
        timeout: IntOrFloat,
        timeout_names: Iterable[str],
        stopped_remotes: Optional[Iterable[str]] = None,
        log_msg: Optional[str] = None,
    ) -> None:
        """Initialize the instance.

        Args:
            cmd_runners: thread names that will execute the command
            targets: thread names to resume
            exp_resumed_targets: thread names expected to be resumed
            stopped_remotes: thread names that are stopped
            timeout: value for smart_resume
            timeout_names: thread names expected to cause timeout
            log_msg: log msg for smart_resume
        """
        super().__init__(
            cmd_runners=cmd_runners,
            targets=targets,
            exp_resumed_targets=exp_resumed_targets,
            stopped_remotes=stopped_remotes,
            timeout=timeout,
            log_msg=log_msg,
        )
        self.specified_args = locals()  # used for __repr__

        self.timeout_names = get_set(timeout_names)

        self.arg_list += ["timeout_names"]

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.handle_resume(
            cmd_runner=cmd_runner,
            targets=self.targets,
            exp_resumed_targets=self.exp_resumed_targets,
            stopped_remotes=self.stopped_remotes,
            timeout=self.timeout,
            timeout_names=self.timeout_names,
            timeout_type=TimeoutType.TimeoutTrue,
            log_msg=self.log_msg,
        )


########################################################################
# SendMsg
########################################################################
class SendMsg(ConfigCmd):
    """Do smart_send."""

    def __init__(
        self,
        cmd_runners: Iterable[str],
        receivers: Iterable[str],
        exp_receivers: Iterable[str],
        msgs_to_send: SendRecvMsgs,
        msg_idx: int,
        send_type: SendType = SendType.ToRemotes,
        stopped_remotes: Optional[Iterable[str]] = None,
        log_msg: Optional[str] = None,
    ) -> None:
        """Initialize the instance.

        Args:
            cmd_runners: thread names that will execute the command
            receivers: thread names that will receive the message
            exp_receivers: thread names expected to receive
            msgs_to_send: messages to send and verify
            msg_idx: index to use with msgs_to_send for this call
            send_type: specifies how to send the messages
            stopped_remotes: thread names that are stopped
            log_msg: log message for smart_send
        """
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        self.receivers = get_set(receivers)
        self.msgs_to_send = msgs_to_send
        self.msg_idx = msg_idx

        self.send_type = send_type

        self.stopped_remotes = get_set(stopped_remotes)

        self.exp_receivers = get_set(exp_receivers)

        self.log_msg = log_msg

        self.arg_list += ["receivers", "stopped_remotes", "send_type", "msg_idx"]

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.handle_send_msg(
            cmd_runner=cmd_runner,
            receivers=self.receivers,
            exp_receivers=self.exp_receivers,
            msgs_to_send=self.msgs_to_send,
            msg_idx=self.msg_idx,
            send_type=self.send_type,
            timeout_type=TimeoutType.TimeoutNone,
            timeout=0,
            unreg_timeout_names=None,
            fullq_timeout_names=None,
            stopped_remotes=self.stopped_remotes,
            log_msg=self.log_msg,
        )


########################################################################
# SendMsgTimeoutFalse
########################################################################
class SendMsgTimeoutFalse(SendMsg):
    """Do smart_send with timeout false."""

    def __init__(
        self,
        cmd_runners: Iterable[str],
        receivers: Iterable[str],
        exp_receivers: Iterable[str],
        msgs_to_send: SendRecvMsgs,
        msg_idx: int,
        timeout: IntOrFloat,
        send_type: SendType = SendType.ToRemotes,
        stopped_remotes: Optional[StrOrSet] = None,
        log_msg: Optional[str] = None,
    ) -> None:
        """Initialize the instance.

        Args:
            cmd_runners: thread names that will execute the command
            receivers: thread names that will receive the message
            exp_receivers: thread names expected to receive
            msgs_to_send: messages to send and verify
            msg_idx: index to use with msgs_to_send for this call
            timeout: value for smart_send
            send_type: specifies how to send the messages
            stopped_remotes: thread names that are stopped
            log_msg: log message for smart_send
        """
        super().__init__(
            cmd_runners=cmd_runners,
            receivers=receivers,
            exp_receivers=exp_receivers,
            msgs_to_send=msgs_to_send,
            msg_idx=msg_idx,
            send_type=send_type,
            stopped_remotes=stopped_remotes,
            log_msg=log_msg,
        )
        self.specified_args = locals()  # used for __repr__

        self.timeout = timeout

        self.arg_list += ["timeout"]

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.handle_send_msg(
            cmd_runner=cmd_runner,
            receivers=self.receivers,
            exp_receivers=self.exp_receivers,
            msgs_to_send=self.msgs_to_send,
            msg_idx=self.msg_idx,
            send_type=self.send_type,
            timeout_type=TimeoutType.TimeoutFalse,
            timeout=self.timeout,
            unreg_timeout_names=None,
            fullq_timeout_names=None,
            stopped_remotes=self.stopped_remotes,
            log_msg=self.log_msg,
        )


########################################################################
# SendMsgTimeoutTrue
########################################################################
class SendMsgTimeoutTrue(SendMsgTimeoutFalse):
    """Do smart_send with timeout true."""

    def __init__(
        self,
        cmd_runners: Iterable[str],
        receivers: Iterable[str],
        exp_receivers: Iterable[str],
        msgs_to_send: SendRecvMsgs,
        msg_idx: int,
        timeout: IntOrFloat,
        unreg_timeout_names: Iterable[str],
        fullq_timeout_names: Iterable[str],
        send_type: SendType = SendType.ToRemotes,
        stopped_remotes: Optional[StrOrSet] = None,
        log_msg: Optional[str] = None,
    ) -> None:
        """Initialize the instance.

        Args:
            cmd_runners: thread names that will execute the command
            receivers: thread names that will receive the message
            exp_receivers: thread names expected to receive
            msgs_to_send: messages to send and verify
            msg_idx: index to use with msgs_to_send for this call
            timeout: value for smart_send
            unreg_timeout_names: thread names that are not registered
            fullq_timeout_names: thread names whose msg_q is full
            send_type: specifies how to send the messages
            stopped_remotes: thread names that are stopped
            log_msg: log message for smart_send
        """
        super().__init__(
            cmd_runners=cmd_runners,
            receivers=receivers,
            exp_receivers=exp_receivers,
            msgs_to_send=msgs_to_send,
            msg_idx=msg_idx,
            timeout=timeout,
            send_type=send_type,
            stopped_remotes=stopped_remotes,
            log_msg=log_msg,
        )
        self.specified_args = locals()  # used for __repr__

        self.arg_list += ["unreg_timeout_names", "fullq_timeout_names"]

        self.unreg_timeout_names = get_set(unreg_timeout_names)

        self.fullq_timeout_names = get_set(fullq_timeout_names)

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.handle_send_msg(
            cmd_runner=cmd_runner,
            receivers=self.receivers,
            exp_receivers=self.exp_receivers,
            msgs_to_send=self.msgs_to_send,
            msg_idx=self.msg_idx,
            send_type=self.send_type,
            timeout_type=TimeoutType.TimeoutTrue,
            timeout=self.timeout,
            unreg_timeout_names=set(self.unreg_timeout_names),
            fullq_timeout_names=set(self.fullq_timeout_names),
            stopped_remotes=self.stopped_remotes,
            log_msg=self.log_msg,
        )


########################################################################
# StartThread
########################################################################
class StartThread(ConfigCmd):
    """Start a thread with smart_start."""

    def __init__(
        self,
        cmd_runners: Iterable[str],
        start_names: Iterable[str],
        unreg_remotes: Optional[Iterable[str]] = None,
        log_msg: Optional[str] = None,
    ) -> None:
        """Initialize the instance.

        Args:
            cmd_runners: thread names that will execute the command
            start_names: thread names to start
            unreg_remotes: thread names that are not registered state
            log_msg: log message for smart_start
        """
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        self.start_names = get_set(start_names)

        self.unreg_remotes = get_set(unreg_remotes)

        self.log_msg = log_msg

        self.arg_list += ["start_names", "unreg_remotes"]

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.handle_start(
            cmd_runner=cmd_runner,
            start_names=self.start_names,
            unreg_remotes=self.unreg_remotes,
            log_msg=self.log_msg,
        )


########################################################################
# StopThread
########################################################################
class StopThread(ConfigCmd):
    """Stop a thread."""

    def __init__(
        self,
        cmd_runners: Iterable[str],
        stop_names: Iterable[str],
        reset_ops_count: bool = False,
        send_recv_msgs: Optional[SendRecvMsgs] = None,
    ) -> None:
        """Initialize the instance.

        Args:
            cmd_runners: thread names that will execute the command
            stop_names: thread names to stop
            reset_ops_count: specifies whether to reset ops count for
                the stop names
            send_recv_msgs: messages to be reset
        """
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        self.stop_names = get_set(stop_names)

        self.reset_ops_count = reset_ops_count

        self.send_recv_msgs = send_recv_msgs

        self.arg_list += ["stop_names", "reset_ops_count"]

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.stop_thread(
            cmd_runner=cmd_runner,
            stop_names=self.stop_names,
            reset_ops_count=self.reset_ops_count,
            send_recv_msgs=self.send_recv_msgs,
        )


########################################################################
# Sync
########################################################################
class Sync(ConfigCmd):
    """Do smart_sync."""

    def __init__(
        self,
        cmd_runners: Iterable[str],
        targets: Iterable[str],
        timeout: IntOrFloat = 0,
        timeout_remotes: Optional[Iterable[str]] = None,
        stopped_remotes: Optional[Iterable[str]] = None,
        deadlock_remotes: Optional[Iterable[str]] = None,
        sync_set_ack_remotes: Optional[Iterable[str]] = None,
        log_msg: Optional[str] = None,
    ) -> None:
        """Initialize the instance.

        Args:
            cmd_runners: thread names that will execute the command
            targets: thread names who will sync with each other
            timeout: value for smart_sync
            timeout_remotes: thread names that cause timeout
            stopped_remotes: thread names that are stopped
            deadlock_remotes: thread names that cause deadlock
            sync_set_ack_remotes: thread names that will get the first
                sync set ack message (but may or may not get the
                achieved sync ack if they fail to respond for timeout or
                stopped scenarios)
            log_msg: log message for smart_sync
        """
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        self.targets = get_set(targets)

        self.timeout = timeout

        self.timeout_remotes = get_set(timeout_remotes)

        self.stopped_remotes = get_set(stopped_remotes)

        self.deadlock_remotes = get_set(deadlock_remotes)

        self.sync_set_ack_remotes = get_set(sync_set_ack_remotes)

        self.log_msg = log_msg

        self.arg_list += [
            "targets",
            "timeout",
            "stopped_remotes",
            "timeout_remotes",
            "deadlock_remotes",
            "sync_set_ack_remotes",
        ]

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        targets = self.targets - {cmd_runner}
        self.config_ver.handle_sync(
            cmd_runner=cmd_runner,
            targets=targets,
            timeout=self.timeout,
            timeout_remotes=self.timeout_remotes,
            stopped_remotes=self.stopped_remotes,
            deadlock_remotes=self.deadlock_remotes,
            sync_set_ack_remotes=self.sync_set_ack_remotes,
            timeout_type=TimeoutType.TimeoutNone,
            log_msg=self.log_msg,
        )


########################################################################
# SyncTimeoutFalse
########################################################################
class SyncTimeoutFalse(Sync):
    """Do smart_sync with timeout of false."""

    def __init__(
        self,
        cmd_runners: Iterable[str],
        targets: Iterable[str],
        timeout: IntOrFloat,
        stopped_remotes: Optional[Iterable[str]] = None,
        timeout_remotes: Optional[Iterable[str]] = None,
        deadlock_remotes: Optional[Iterable[str]] = None,
        sync_set_ack_remotes: Optional[Iterable[str]] = None,
        log_msg: Optional[str] = None,
    ) -> None:
        """Initialize the instance.

        Args:
            cmd_runners: thread names that will execute the command
            targets: thread names who will sync with each other
            timeout: value for smart_sync
            timeout_remotes: thread names that cause timeout
            stopped_remotes: thread names that are stopped
            deadlock_remotes: thread names that cause deadlock
            sync_set_ack_remotes: thread names that will get the first
                sync set ack message (but may or may not get the
                achieved sync ack if they fail to respond for timeout or
                stopped scenarios)
            log_msg: log message for smart_sync
        """
        super().__init__(
            cmd_runners=cmd_runners,
            targets=targets,
            timeout=timeout,
            timeout_remotes=timeout_remotes,
            stopped_remotes=stopped_remotes,
            deadlock_remotes=deadlock_remotes,
            sync_set_ack_remotes=sync_set_ack_remotes,
            log_msg=log_msg,
        )
        self.specified_args = locals()  # used for __repr__

        self.arg_list += ["timeout"]

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        targets = self.targets - {cmd_runner}
        self.config_ver.handle_sync(
            cmd_runner=cmd_runner,
            targets=targets,
            timeout=self.timeout,
            timeout_remotes=self.timeout_remotes,
            stopped_remotes=self.stopped_remotes,
            deadlock_remotes=self.deadlock_remotes,
            sync_set_ack_remotes=self.sync_set_ack_remotes,
            timeout_type=TimeoutType.TimeoutFalse,
            log_msg=self.log_msg,
        )


########################################################################
# SyncTimeoutFalse
########################################################################
class SyncTimeoutTrue(SyncTimeoutFalse):
    """Do smart_sync with timeout of true."""

    def __init__(
        self,
        cmd_runners: Iterable[str],
        targets: Iterable[str],
        timeout: IntOrFloat,
        timeout_remotes: Iterable[str],
        stopped_remotes: Optional[Iterable[str]] = None,
        deadlock_remotes: Optional[Iterable[str]] = None,
        sync_set_ack_remotes: Optional[Iterable[str]] = None,
        log_msg: Optional[str] = None,
    ) -> None:
        """Initialize the instance.

        Args:
            cmd_runners: thread names that will execute the command
            targets: thread names who will sync with each other
            timeout: value for smart_sync
            timeout_remotes: thread names that cause timeout
            stopped_remotes: thread names that are stopped
            deadlock_remotes: thread names that cause deadlock
            sync_set_ack_remotes: thread names that will get the first
                sync set ack message (but may or may not get the
                achieved sync ack if they fail to respond for timeout or
                stopped scenarios)
            log_msg: log message for smart_sync
        """
        super().__init__(
            cmd_runners=cmd_runners,
            targets=targets,
            timeout=timeout,
            timeout_remotes=timeout_remotes,
            stopped_remotes=stopped_remotes,
            deadlock_remotes=deadlock_remotes,
            sync_set_ack_remotes=sync_set_ack_remotes,
            log_msg=log_msg,
        )
        self.specified_args = locals()  # used for __repr__

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        targets = self.targets - {cmd_runner}
        self.config_ver.handle_sync(
            cmd_runner=cmd_runner,
            targets=targets,
            timeout=self.timeout,
            timeout_remotes=self.timeout_remotes,
            stopped_remotes=self.stopped_remotes,
            deadlock_remotes=self.deadlock_remotes,
            sync_set_ack_remotes=self.sync_set_ack_remotes,
            timeout_type=TimeoutType.TimeoutTrue,
            log_msg=self.log_msg,
        )


########################################################################
# Unregister
########################################################################
class Unregister(ConfigCmd):
    """Do the smart_unreg."""

    def __init__(
        self,
        cmd_runners: Iterable[str],
        unregister_targets: Iterable[str],
        not_registered_remotes: Optional[Iterable[str]] = None,
        log_msg: Optional[str] = None,
        post_main_driver: bool = False,
    ) -> None:
        """Initialize the instance.

        Args:
            cmd_runners: thread names that will execute the command
            unregister_targets: thread names to be unregistered
            not_registered_remotes: remotes not registered that should
                result in error
            log_msg: log message for smart_unreg
            post_main_driver: requested by main driver when unreg is
                done for all remaining f1 threads and commander thread
        """
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        self.unregister_targets = get_set(unregister_targets)

        self.not_registered_remotes = get_set(not_registered_remotes)

        self.log_msg = log_msg

        self.post_main_driver = post_main_driver

        self.arg_list += ["unregister_targets", "not_registered_remotes"]

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.handle_unregister(
            cmd_runner=cmd_runner,
            unregister_targets=self.unregister_targets,
            not_registered_remotes=self.not_registered_remotes,
            log_msg=self.log_msg,
            post_main_driver=self.post_main_driver,
        )


########################################################################
# ValidateConfig
########################################################################
class VerifyConfig(ConfigCmd):
    """Validate the configuration."""

    def __init__(
        self,
        cmd_runners: Iterable[str],
        verify_type: VerifyType,
        names_to_check: Optional[Iterable[str]] = None,
        aux_names: Optional[Iterable[str]] = None,
        state_to_check: st.ThreadState = st.ThreadState.Unregistered,
        exp_pending_flags: PendingFlags = PendingFlags(),
        obtain_reg_lock: bool = True,
    ) -> None:
        """Initialize the instance.

        Args:
            cmd_runners: thread names that will execute the command
            verify_type: type of verification to do
            names_to_check: thread names to verify
            aux_names: thread names associated with names_to_check
            state_to_check: expected ThreadState
            exp_pending_flags: expected pending flags
            obtain_reg_lock: if True, obtain the smart_thread lock

        """
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        self.verify_type = verify_type
        self.names_to_check = get_set(names_to_check)
        self.aux_names = get_set(aux_names)
        self.state_to_check = state_to_check
        self.exp_pending_flags = exp_pending_flags
        self.obtain_reg_lock = obtain_reg_lock

        self.arg_list += [
            "verify_type",
            "names_to_check",
            "aux_names",
            "state_to_check",
            "exp_pending_flags",
        ]

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        verify_data: VerifyData = VerifyData(
            cmd_runner=cmd_runner,
            verify_type=self.verify_type,
            names_to_check=self.names_to_check,
            aux_names=self.aux_names,
            state_to_check=self.state_to_check,
            exp_pending_flags=self.exp_pending_flags,
            obtain_reg_lock=self.obtain_reg_lock,
        )

        self.config_ver.create_snapshot_data(
            verify_name="verify_config",
            verify_idx=self.serial_num,
            verify_data=verify_data,
        )

        if self.config_ver.verify_config_complete_event.wait(timeout=60):
            self.config_ver.verify_config_complete_event.clear()
        else:
            self.config_ver.abort_test_case()


########################################################################
# VerifyCounts
########################################################################
class VerifyCounts(ConfigCmd):
    """Verify the number of threads at various states in the config."""

    def __init__(
        self,
        cmd_runners: Iterable[str],
        exp_num_registered: int,
        exp_num_active: int,
        exp_num_stopped: int,
    ) -> None:
        """Initialize the instance.

        Args:
            cmd_runners: thread names that will execute the command
            exp_num_registered: number thread expected to be registered
                state
            exp_num_active: number thread expected to be alive state
            exp_num_stopped: number thread expected to be stopped state
        """
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        self.exp_num_registered = exp_num_registered
        self.exp_num_active = exp_num_active
        self.exp_num_stopped = exp_num_stopped

        self.arg_list += ["exp_num_registered", "exp_num_active", "exp_num_stopped"]

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        verify_data: VerifyData = VerifyData(
            cmd_runner=cmd_runner,
            verify_type=VerifyType.VerifyCounts,
            names_to_check=set(),
            aux_names=set(),
            state_to_check=st.ThreadState.Alive,
            exp_pending_flags=PendingFlags(),
            obtain_reg_lock=True,
            num_registered=self.exp_num_registered,
            num_active=self.exp_num_active,
            num_stopped=self.exp_num_stopped,
        )
        self.config_ver.create_snapshot_data(
            verify_name="verify_counts",
            verify_idx=self.serial_num,
            verify_data=verify_data,
        )


########################################################################
# VerifyCounts
########################################################################
class VerifyGetSmartThreadNames(ConfigCmd):
    """Verify the number of threads at various states in the config."""

    def __init__(
        self,
        cmd_runners: Iterable[str],
        registered_names: Optional[Iterable[str]] = None,
        alive_names: Optional[Iterable[str]] = None,
        stopped_names: Optional[Iterable[str]] = None,
    ) -> None:
        """Initialize the instance.

        Args:
            cmd_runners: thread names that will execute the command
            registered_names: names of threads that are registered
            alive_names: names of threads that are alive
            stopped_names: names of threads that are stopped
        """
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        self.registered_names = get_set(registered_names)
        self.alive_names = get_set(alive_names)
        self.stopped_names = get_set(stopped_names)

        self.arg_list += ["registered_names", "alive_names", "stopped_names"]

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.handle_get_smart_thread_names(
            cmd_runner=cmd_runner,
            registered_names=self.registered_names,
            alive_names=self.alive_names,
            stopped_names=self.stopped_names,
        )


########################################################################
# VerifyDefDel
########################################################################
class VerifyDefDel(ConfigCmd):
    """Verify deferred deletes."""

    def __init__(
        self,
        cmd_runners: Iterable[str],
        def_del_scenario: DefDelScenario,
        receiver_names: list[str],
        sender_names: list[str],
        waiter_names: list[str],
        resumer_names: list[str],
        del_names: list[str],
        add_names: list[str],
        deleter_names: list[str],
        adder_names: list[str],
    ) -> None:
        """Initialize the instance.

        Args:
            cmd_runners: thread names that will execute the command
            def_del_scenario: scenario to run
            receiver_names: thread names
            sender_names: thread names
            waiter_names: thread names
            resumer_names: thread names
            del_names: thread names
            add_names: thread names
            deleter_names: thread names
            adder_names: thread names
        """
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        self.def_del_scenario = def_del_scenario
        self.receiver_names = receiver_names
        self.sender_names = sender_names
        self.waiter_names = waiter_names
        self.resumer_names = resumer_names
        self.del_names = del_names
        self.add_names = add_names
        self.deleter_names = deleter_names
        self.adder_names = adder_names

        self.arg_list += ["def_del_scenario"]

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.verify_def_del(
            cmd_runner=cmd_runner,
            def_del_scenario=self.def_del_scenario,
            receiver_names=self.receiver_names,
            sender_names=self.sender_names,
            waiter_names=self.waiter_names,
            resumer_names=self.resumer_names,
            del_names=self.del_names,
            add_names=self.add_names,
            deleter_names=self.deleter_names,
            adder_names=self.adder_names,
        )


########################################################################
# Wait
########################################################################
class Wait(ConfigCmd):
    """Do smart_wait."""

    def __init__(
        self,
        cmd_runners: Iterable[str],
        resumers: Iterable[str],
        exp_resumers: Iterable[str],
        resumer_count: Optional[int] = None,
        stopped_remotes: Optional[Iterable[str]] = None,
        deadlock_remotes: Optional[Iterable[str]] = None,
        log_msg: Optional[str] = None,
    ) -> None:
        """Initialize the instance.

        Args:
            cmd_runners: thread names that will execute the command
            resumers: thread names that will resume
            exp_resumers: thread names that the wait is expected to be
                resumed by
            resumer_count: specification for smart_wait for how many
                resumes are needed to satisfy the smart_wait
            stopped_remotes: thread names that are stopped
            deadlock_remotes: thread names that cause deadlock
            log_msg: log message for the smart_resume
        """
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        self.resumers = get_set(resumers)
        self.exp_resumers = get_set(exp_resumers)

        self.stopped_remotes = get_set(stopped_remotes)

        self.deadlock_remotes = get_set(deadlock_remotes)

        self.resumer_count = resumer_count

        self.log_msg = log_msg

        self.arg_list += [
            "resumers",
            "exp_resumers",
            "resumer_count",
            "stopped_remotes",
            "deadlock_remotes",
        ]

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.handle_wait(
            cmd_runner=cmd_runner,
            resumers=self.resumers,
            exp_resumers=self.exp_resumers,
            timeout=0,
            timeout_remotes=set(),
            stopped_remotes=self.stopped_remotes,
            deadlock_remotes=self.deadlock_remotes,
            deadlock_or_timeout=False,
            timeout_type=TimeoutType.TimeoutNone,
            resumer_count=self.resumer_count,
            log_msg=self.log_msg,
        )


########################################################################
# WaitTimeoutFalse
########################################################################
class WaitTimeoutFalse(Wait):
    """Do smart_wait with timeout false."""

    def __init__(
        self,
        cmd_runners: Iterable[str],
        resumers: Iterable[str],
        exp_resumers: Iterable[str],
        timeout: IntOrFloat,
        resumer_count: Optional[int] = None,
        stopped_remotes: Optional[Iterable[str]] = None,
        deadlock_remotes: Optional[Iterable[str]] = None,
        log_msg: Optional[str] = None,
    ) -> None:
        """Initialize the instance.

        Args:
            cmd_runners: thread names that will execute the command
            resumers: thread names that will do the smart_resume
            exp_resumers: thread names that the wait is expected to be
                resumed by
            timeout: value for smart_wait
            resumer_count: specification for smart_wait for how many
                resumes are needed to satisfy the smart_wait
            stopped_remotes: thread names that are stopped
            deadlock_remotes: thread names that are deadlocked
            log_msg: log message for smart_wait
        """
        super().__init__(
            cmd_runners=cmd_runners,
            resumers=resumers,
            exp_resumers=exp_resumers,
            stopped_remotes=stopped_remotes,
            resumer_count=resumer_count,
            deadlock_remotes=deadlock_remotes,
            log_msg=log_msg,
        )
        self.specified_args = locals()  # used for __repr__

        self.timeout = timeout

        self.arg_list += ["timeout"]

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.handle_wait(
            cmd_runner=cmd_runner,
            resumers=self.resumers,
            exp_resumers=self.exp_resumers,
            timeout=self.timeout,
            timeout_remotes=set(),
            stopped_remotes=self.stopped_remotes,
            deadlock_remotes=self.deadlock_remotes,
            deadlock_or_timeout=False,
            timeout_type=TimeoutType.TimeoutFalse,
            resumer_count=self.resumer_count,
            log_msg=self.log_msg,
        )


########################################################################
# WaitTimeoutTrue
########################################################################
class WaitTimeoutTrue(WaitTimeoutFalse):
    """Do smart_wait with timeout true."""

    def __init__(
        self,
        cmd_runners: Iterable[str],
        resumers: Iterable[str],
        exp_resumers: Iterable[str],
        timeout: IntOrFloat,
        timeout_remotes: Iterable[str],
        resumer_count: Optional[int] = None,
        stopped_remotes: Optional[Iterable[str]] = None,
        deadlock_remotes: Optional[Iterable[str]] = None,
        deadlock_or_timeout: bool = False,
        log_msg: Optional[str] = None,
    ) -> None:
        """Initialize the instance.

        Args:
            cmd_runners: thread names that will execute the command
            resumers: thread names that will do the smart_resume
            exp_resumers: thread names that the wait is expected to be
                resumed by
            timeout: value for smart_wait
            timeout_remotes: thread names that cause a timeout
            resumer_count: specification for smart_wait for how many
                resumes are needed to satisfy the smart_wait
            stopped_remotes: thread names that are stopped
            deadlock_remotes: thread names that are deadlocked
            deadlock_or_timeout: expect either deadlock or timeout
            log_msg: log message for smart_wait
        """
        super().__init__(
            cmd_runners=cmd_runners,
            resumers=resumers,
            exp_resumers=exp_resumers,
            stopped_remotes=stopped_remotes,
            resumer_count=resumer_count,
            deadlock_remotes=deadlock_remotes,
            timeout=timeout,
            log_msg=log_msg,
        )
        self.specified_args = locals()  # used for __repr__

        self.timeout_remotes = get_set(timeout_remotes)

        self.deadlock_or_timeout = deadlock_or_timeout

        self.arg_list += ["timeout_remotes"]

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.handle_wait(
            cmd_runner=cmd_runner,
            resumers=self.resumers,
            exp_resumers=self.exp_resumers,
            timeout=self.timeout,
            timeout_remotes=self.timeout_remotes,
            stopped_remotes=self.stopped_remotes,
            deadlock_remotes=self.deadlock_remotes,
            deadlock_or_timeout=self.deadlock_or_timeout,
            timeout_type=TimeoutType.TimeoutTrue,
            resumer_count=self.resumer_count,
            log_msg=self.log_msg,
        )


########################################################################
# WaitForCondition
########################################################################
class WaitForCondition(ConfigCmd):
    """Wait for receive message timeouts."""

    def __init__(
        self,
        cmd_runners: Iterable[str],
        check_rtn: Callable[..., bool],
        check_args: Any,
    ) -> None:
        """Initialize the instance.

        Args:
            cmd_runners: thread names that will execute the command
            check_rtn: routine that will do the check
            check_args: the arguments for the check_rtn

        """
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__
        self.check_rtn = check_rtn
        self.check_args = check_args

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        start_time = time.time()
        while not self.check_rtn(cmd_runner=cmd_runner, check_args=self.check_args):
            time.sleep(0.1)
            if start_time + 30 < time.time():
                raise CmdTimedOut("WaitForCondition timed out")


########################################################################
# WaitForRecvTimeouts
########################################################################
class WaitForRecvTimeouts(ConfigCmd):
    """Wait for receive message timeouts."""

    def __init__(self, cmd_runners: Iterable[str]) -> None:
        """Initialize the instance.

        Args:
            cmd_runners: thread names that will execute the command

        """
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.wait_for_recv_msg_timeouts(cmd_runner=cmd_runner)


########################################################################
# WaitForRequestTimeouts
########################################################################
class WaitForRequestTimeouts(ConfigCmd):
    """Wait for request timeouts command."""

    def __init__(
        self,
        cmd_runners: Iterable[str],
        actor_names: Iterable[str],
        timeout_names: Iterable[str],
        use_work_remotes: bool = False,
        as_subset: bool = False,
    ) -> None:
        """Initialize the instance.

        Args:
            cmd_runners: thread names that will execute the command
            actor_names: thread names that are cmd runners waiting for a
                timeout or timeout condition
            timeout_names: thread names that are expected to cause
                timeout by not responding or by not being alive
            use_work_remotes: if True, compare against work_remotes,
                else pk_remotes
            as_subset: if True, the wait is satisfied when the
                timeout_names are a subset of the pk_remotes
        """
        super().__init__(cmd_runners=cmd_runners)
        self.specified_args = locals()  # used for __repr__

        self.actor_names = get_set(actor_names)

        self.timeout_names = get_set(timeout_names)

        self.use_work_remotes = use_work_remotes

        self.as_subset = as_subset

        self.arg_list += [
            "actor_names",
            "timeout_names",
            "use_work_remotes",
            "as_subset",
        ]

    def run_process(self, cmd_runner: str) -> None:
        """Run the command.

        Args:
            cmd_runner: name of thread running the command
        """
        self.config_ver.wait_for_request_timeouts(
            cmd_runner=cmd_runner,
            actor_names=self.actor_names,
            timeout_names=self.timeout_names,
            use_work_remotes=self.use_work_remotes,
            as_subset=self.as_subset,
        )


########################################################################
# F1CreateItem
########################################################################
@dataclass
class F1CreateItem:
    """Class that has infor for f1 create."""

    name: str
    auto_start: bool
    target_rtn: Callable[..., Any]
    app_config: AppConfig = AppConfig.ScriptStyle


########################################################################
# TestSmartThreadLogMsgs class
########################################################################
@dataclass
class ThreadTracker:
    """Class that tracks each thread."""

    thread: st.SmartThread
    is_alive: bool
    exiting: bool
    is_auto_started: bool
    is_TargetThread: bool
    exp_init_is_alive: bool
    thread_create: st.ThreadCreate
    exp_init_thread_state: st.ThreadState
    auto_start_decision: AutoStartDecision
    st_state: st.ThreadState
    found_del_pairs: dict[tuple[str, str, str], int]
    stopped_by: str = ""
    reg_to_unreg: bool = False
    stopped_to_unreg: bool = False


@dataclass
class ThreadPairStatus:
    """Class that keeps pair status."""

    reset_ops_count: bool
    pending_request: bool = False
    pending_msg_count: int = 0
    pending_wait: bool = False
    pending_wait_count: int = 0
    pending_sync: bool = False


@dataclass
class MonitorAddItem:
    """Class keeps track of threads to add, start, delete, unreg."""

    cmd_runner: str
    thread_alive: bool
    auto_start: bool
    is_ThreadTarget: bool
    expected_state: st.ThreadState


@dataclass
class UpaItem:
    """Update pair_array item."""

    upa_cmd_runner: str
    upa_type: str
    upa_target: str
    upa_def_del_name: str
    upa_process: str


@dataclass
class MonitorEventItem:
    """Class keeps track of threads to add, start, delete, unreg."""

    client_event: threading.Event
    targets: set[str]
    deferred_post_needed: bool = False


hour_match = "([01][0-9]|20|21|22|23)"
min_sec_match = "[0-5][0-9]"
micro_sec_match = "[0-9]{6,6}"
time_match = rf"{hour_match}:{min_sec_match}:{min_sec_match}\." f"{micro_sec_match}"

list_of_thread_states = (
    "(ThreadState.Unregistered"
    "|ThreadState.Initialized"
    "|ThreadState.Registered"
    "|ThreadState.Alive"
    "|ThreadState.Stopped)"
)

list_of_smart_requests = (
    "(smart_init"
    "|smart_start"
    "|smart_unreg"
    "|smart_join"
    "|smart_send"
    "|smart_recv"
    "|smart_wait"
    "|smart_resume"
    "|smart_sync)"
)

list_of_sub_processes = (
    "(_register" "|_clean_registry" "|_clean_pair_array" "|_add_to_pair_array)"
)

smart_reqs = ("smart_send", "smart_recv", "smart_wait", "smart_resume", "smart_sync")


########################################################################
# LogSearchItem
########################################################################
class LogSearchItem(ABC):
    """Input to search log msgs."""

    def __init__(
        self,
        search_str: str,
        config_ver: "ConfigVerifier",
        found_log_msg: str = "",
        found_log_idx: int = 0,
    ) -> None:
        """Initialize the LogItem.

        Args:
            search_str: regex style search string
            config_ver: configuration verifier
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found
        """
        self.search_pattern = re.compile(search_str)
        self.config_ver: "ConfigVerifier" = config_ver
        self.found_log_msg = found_log_msg
        self.found_log_idx = found_log_idx

    @abstractmethod
    def get_found_log_item(
        self, found_log_msg: str, found_log_idx: int
    ) -> "LogSearchItem":
        """Return a found log item.

        Args:
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found

        Returns:
            LogFoundItem containing found message and index
        """
        pass

    @abstractmethod
    def run_process(self) -> None:
        """Run the process to handle the log message."""
        pass


########################################################################
# RequestEntryExitLogSearchItem
########################################################################
class RequestEntryExitLogSearchItem(LogSearchItem):
    """Input to search log msgs."""

    def __init__(
        self,
        config_ver: "ConfigVerifier",
        found_log_msg: str = "",
        found_log_idx: int = 0,
    ) -> None:
        """Initialize the LogItem.

        Args:
            config_ver: configuration verifier
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found
        """
        super().__init__(
            search_str=(
                f"{list_of_smart_requests} (entry|exit): "
                rf"requestor: [a-z0-9_]+ \({config_ver.group_name}\), "
                r"targets: \[([a-z0-9_]*|,|'| )*\]"
            ),
            config_ver=config_ver,
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
        )

    def get_found_log_item(
        self, found_log_msg: str, found_log_idx: int
    ) -> "RequestEntryExitLogSearchItem":
        """Return a found log item.

        Args:
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found

        Returns:
            SyncResumedLogSearchItem containing found message and index
        """
        return RequestEntryExitLogSearchItem(
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
            config_ver=self.config_ver,
        )

    def run_process(self) -> None:
        """Run the process to handle the log message."""
        split_msg = self.found_log_msg.split()
        request_name = split_msg[0]
        entry_exit = split_msg[1][0:-1]  # remove colon
        cmd_runner = split_msg[3]
        target_msg = self.found_log_msg.split("[")[1].split("]")[0].split(", ")

        targets: list[str] = []
        for item in target_msg:
            targets.append(item[1:-1])

        if not targets:
            targets = [""]

        self.config_ver.handle_request_entry_exit_log_msg(
            cmd_runner=cmd_runner,
            request_name=request_name,
            entry_exit=entry_exit,
            targets=targets,
            log_msg=self.found_log_msg,
        )


########################################################################
# SetupCompleteLogSearchItem
########################################################################
class SetupCompleteLogSearchItem(LogSearchItem):
    """Input to search log msgs."""

    def __init__(
        self,
        config_ver: "ConfigVerifier",
        found_log_msg: str = "",
        found_log_idx: int = 0,
    ) -> None:
        """Initialize the LogItem.

        Args:
            config_ver: configuration verifier
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found
        """
        super().__init__(
            search_str=(
                rf"SmartThread [a-z0-9_]+ \({config_ver.group_name}\) "
                f"{list_of_smart_requests} setup complete for targets: "
            ),
            config_ver=config_ver,
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
        )

    def get_found_log_item(
        self, found_log_msg: str, found_log_idx: int
    ) -> "SetupCompleteLogSearchItem":
        """Return a found log item.

        Args:
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found

        Returns:
            SyncResumedLogSearchItem containing found message and index
        """
        return SetupCompleteLogSearchItem(
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
            config_ver=self.config_ver,
        )

    def run_process(self) -> None:
        """Run the process to handle the log message."""
        split_msg = self.found_log_msg.split()
        cmd_runner = split_msg[1]
        request_name = split_msg[3]
        target_msg = self.found_log_msg.split("[")[1].split("]")[0].split(", ")

        targets: list[str] = []
        for item in target_msg:
            if item.startswith("remote="):
                target = item[8:-1]
                targets.append(target)

        if request_name in (
            "smart_send",
            "smart_recv",
            "smart_wait",
            "smart_resume",
            "smart_sync",
        ):
            self.config_ver.set_request_pending_flag(
                cmd_runner=cmd_runner, targets=set(targets), pending_request_flag=True
            )

        self.config_ver.add_log_msg(re.escape(self.found_log_msg))


########################################################################
# SubProcessEntryExitLogSearchItem
########################################################################
class SubProcessEntryExitLogSearchItem(LogSearchItem):
    """Input to search log msgs."""

    def __init__(
        self,
        config_ver: "ConfigVerifier",
        found_log_msg: str = "",
        found_log_idx: int = 0,
    ) -> None:
        """Initialize the LogItem.

        Args:
            config_ver: configuration verifier
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found
        """
        super().__init__(
            search_str=(
                f"{list_of_smart_requests} {list_of_sub_processes} (entry|exit): "
                rf"[a-z0-9_]+ \({config_ver.group_name}\)(, target: [a-z0-9_]+)*"
            ),
            config_ver=config_ver,
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
        )

    def get_found_log_item(
        self, found_log_msg: str, found_log_idx: int
    ) -> "SubProcessEntryExitLogSearchItem":
        """Return a found log item.

        Args:
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found

        Returns:
            SyncResumedLogSearchItem containing found message and index
        """
        return SubProcessEntryExitLogSearchItem(
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
            config_ver=self.config_ver,
        )

    def run_process(self) -> None:
        """Run the process to handle the log message."""
        split_msg = self.found_log_msg.split()
        request_name = split_msg[0]
        subprocess_name = split_msg[1]
        entry_exit = split_msg[2][0:-1]  # remove trailing colon
        cmd_runner = split_msg[3]
        # if split_msg[-2] == "target:":
        #     cmd_runner = cmd_runner[0:-1]  # remove trailing comma
        if split_msg[-2] == "target:":
            target = split_msg[-1]
        else:
            target = split_msg[-2]

        if subprocess_name == "_clean_registry":
            self.config_ver.last_clean_reg_msg_idx = self.found_log_idx

        self.config_ver.handle_subprocess_entry_exit_log_msg(
            cmd_runner=cmd_runner,
            request_name=request_name,
            subprocess_name=subprocess_name,
            entry_exit=entry_exit,
            target=target,
            log_msg=self.found_log_msg,
        )


########################################################################
# SetStateLogSearchItem
########################################################################
class SetStateLogSearchItem(LogSearchItem):
    """Input to search log msgs."""

    def __init__(
        self,
        config_ver: "ConfigVerifier",
        found_log_msg: str = "",
        found_log_idx: int = 0,
    ) -> None:
        """Initialize the LogItem.

        Args:
            config_ver: configuration verifier
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found
        """
        super().__init__(
            search_str=(
                rf"SmartThread [a-z0-9_]+ \({config_ver.group_name}\) set state for "
                f"thread [a-z0-9_]+ from {list_of_thread_states} to "
                f"{list_of_thread_states}"
            ),
            config_ver=config_ver,
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
        )

    def get_found_log_item(
        self, found_log_msg: str, found_log_idx: int
    ) -> "SetStateLogSearchItem":
        """Return a found log item.

        Args:
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found

        Returns:
            SetStateLogSearchItem containing found message and index
        """
        return SetStateLogSearchItem(
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
            config_ver=self.config_ver,
        )

    def run_process(self) -> None:
        """Run the process to handle the log message."""
        split_msg = self.found_log_msg.split()
        cmd_runner = split_msg[1]
        target_name = split_msg[7]
        from_state_str = split_msg[9]
        to_state_str = split_msg[11]

        from_state = eval("st." + from_state_str)
        to_state = eval("st." + to_state_str)

        self.config_ver.handle_set_state_log_msg(
            cmd_runner=cmd_runner,
            target=target_name,
            from_state=from_state,
            to_state=to_state,
            log_msg=self.found_log_msg,
        )


########################################################################
# InitCompleteLogSearchItem
########################################################################
class InitCompleteLogSearchItem(LogSearchItem):
    """Input to search log msgs."""

    def __init__(
        self,
        config_ver: "ConfigVerifier",
        found_log_msg: str = "",
        found_log_idx: int = 0,
    ) -> None:
        """Initialize the LogItem.

        Args:
            config_ver: configuration verifier
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found
        """
        list_of_thread_creates = (
            "(ThreadCreate.Current" "|ThreadCreate.Target" "|ThreadCreate.Thread)"
        )

        list_of_auto_start_texts = (
            "(auto_start obviated"
            "|auto_start will proceed"
            "|auto_start not requested)"
        )
        super().__init__(
            search_str=(
                rf"SmartThread [a-z0-9_]+ \({config_ver.group_name}\) completed "
                "initialization of [a-z0-9_]+: "
                f"{list_of_thread_creates}, "
                f"{list_of_thread_states}, "
                f"{list_of_auto_start_texts}."
            ),
            config_ver=config_ver,
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
        )

    def get_found_log_item(
        self, found_log_msg: str, found_log_idx: int
    ) -> "InitCompleteLogSearchItem":
        """Return a found log item.

        Args:
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found

        Returns:
            InitCompleteLogSearchItem containing found message and index
        """
        return InitCompleteLogSearchItem(
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
            config_ver=self.config_ver,
        )

    def run_process(self) -> None:
        """Run the process to handle the log message."""
        split_msg = self.found_log_msg.split()
        cmd_runner = split_msg[1]
        target_name = split_msg[6][0:-1]
        create_text = split_msg[7][0:-1]
        state_text = split_msg[8][0:-1]

        thread_create = eval("st." + create_text)
        thread_state = eval("st." + state_text)

        if (
            init_complete_text_units[AutoStartDecision.auto_start_obviated]
            in self.found_log_msg
        ):
            auto_start = AutoStartDecision.auto_start_obviated
        elif (
            init_complete_text_units[AutoStartDecision.auto_start_yes]
            in self.found_log_msg
        ):
            auto_start = AutoStartDecision.auto_start_yes
        elif (
            init_complete_text_units[AutoStartDecision.auto_start_no]
            in self.found_log_msg
        ):
            auto_start = AutoStartDecision.auto_start_no
        else:
            raise InvalidInputDetected(
                "InitCompleteLogSearchItem encountered log msg with "
                f"unknown auto_start text: {self.found_log_msg}"
            )

        pe = self.config_ver.pending_events[cmd_runner]

        comp_key: InitCompKey = (target_name, thread_create, thread_state, auto_start)

        if pe[PE.init_comp_msg][comp_key] <= 0:
            raise UnexpectedEvent(
                f"InitCompleteLogSearchItem using {comp_key=} encountered "
                f"unexpected log message: {self.found_log_msg}"
            )

        pe[PE.init_comp_msg][comp_key] -= 1

        self.config_ver.add_log_msg(
            re.escape(self.found_log_msg), log_level=logging.INFO
        )


########################################################################
# F1AppExitLogSearchItem
########################################################################
class F1AppExitLogSearchItem(LogSearchItem):
    """Input to search log msgs."""

    def __init__(
        self,
        config_ver: "ConfigVerifier",
        found_log_msg: str = "",
        found_log_idx: int = 0,
    ) -> None:
        """Initialize the LogItem.

        Args:
            config_ver: configuration verifier
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found
        """
        list_of_thread_apps = r"(OuterF1ThreadApp.run\(\)" "|outer_f1)"
        super().__init__(
            # search_str=r'OuterF1ThreadApp.run\(\) exit: [a-z0-9_]+',
            search_str=(
                f"{list_of_thread_apps} exit: [a-z0-9_]+ "
                rf"\({config_ver.group_name}\)"
            ),
            config_ver=config_ver,
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
        )

    def get_found_log_item(
        self, found_log_msg: str, found_log_idx: int
    ) -> "F1AppExitLogSearchItem":
        """Return a found log item.

        Args:
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found

        Returns:
            F1AppExitLogSearchItem containing found message and index
        """
        return F1AppExitLogSearchItem(
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
            config_ver=self.config_ver,
        )

    def run_process(self) -> None:
        """Run the process to handle the log message."""
        split_msg = self.found_log_msg.split()
        target = split_msg[2]

        self.config_ver.expected_registered[target].is_alive = False

        self.config_ver.last_thread_stop_msg_idx[target] = self.found_log_idx


########################################################################
# AlreadyUnregLogSearchItem
########################################################################
class AlreadyUnregLogSearchItem(LogSearchItem):
    """Input to search log msgs."""

    def __init__(
        self,
        config_ver: "ConfigVerifier",
        found_log_msg: str = "",
        found_log_idx: int = 0,
    ) -> None:
        """Initialize the LogItem.

        Args:
            config_ver: configuration verifier
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found
        """
        super().__init__(
            search_str=(
                rf"SmartThread [a-z0-9_]+ \({config_ver.group_name}\) determined that "
                "thread [a-z0-9_]+ is already in state ThreadState.Unregistered"
            ),
            config_ver=config_ver,
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
        )

    def get_found_log_item(
        self, found_log_msg: str, found_log_idx: int
    ) -> "AlreadyUnregLogSearchItem":
        """Return a found log item.

        Args:
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found

        Returns:
            AlreadyUnregLogSearchItem containing found message and index
        """
        return AlreadyUnregLogSearchItem(
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
            config_ver=self.config_ver,
        )

    def run_process(self) -> None:
        """Run the process to handle the log message."""
        split_msg = self.found_log_msg.split()
        cmd_runner = split_msg[1]
        target = split_msg[6]

        pe = self.config_ver.pending_events[cmd_runner]
        unreg_key: AlreadyUnregKey = (cmd_runner, target)
        if pe[PE.already_unreg_msg][unreg_key] <= 0:
            raise UnexpectedEvent(
                f"AlreadyUnregLogSearchItem using {unreg_key=} encountered "
                f"unexpected log message: {self.found_log_msg}"
            )

        pe[PE.already_unreg_msg][unreg_key] -= 1

        self.config_ver.add_log_msg(re.escape(self.found_log_msg))


########################################################################
# AddRegEntryLogSearchItem
########################################################################
class AddRegEntryLogSearchItem(LogSearchItem):
    """Input to search log msgs."""

    def __init__(
        self,
        config_ver: "ConfigVerifier",
        found_log_msg: str = "",
        found_log_idx: int = 0,
    ) -> None:
        """Initialize the LogItem.

        Args:
            config_ver: configuration verifier
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found
        """
        super().__init__(
            search_str=(
                rf"SmartThread [a-z0-9_]+ \({config_ver.group_name}\) added [a-z0-9_]+ "
                f"to SmartThread registry at UTC {time_match}"
            ),
            config_ver=config_ver,
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
        )

    def get_found_log_item(
        self, found_log_msg: str, found_log_idx: int
    ) -> "AddRegEntryLogSearchItem":
        """Return a found log item.

        Args:
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found

        Returns:
            AddRegEntryLogSearchItem containing found message and index
        """
        return AddRegEntryLogSearchItem(
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
            config_ver=self.config_ver,
        )

    def run_process(self) -> None:
        """Run the process to handle the log message."""
        split_msg = self.found_log_msg.split()
        self.config_ver.handle_add_reg_log_msg(
            cmd_runner=split_msg[1], target=split_msg[4], log_msg=self.found_log_msg
        )


########################################################################
# AddPairArrayEntryLogSearchItem
########################################################################
class AddPairArrayEntryLogSearchItem(LogSearchItem):
    """Input to search log msgs."""

    def __init__(
        self,
        config_ver: "ConfigVerifier",
        found_log_msg: str = "",
        found_log_idx: int = 0,
    ) -> None:
        """Initialize the LogItem.

        Args:
            config_ver: configuration verifier
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found
        """
        super().__init__(
            search_str=(
                rf"SmartThread [a-z0-9_]+ \({config_ver.group_name}\) added "
                r"PairKey\(name0='[a-z0-9_]+', name1='[a-z0-9_]+'\) "
                "to the pair_array"
            ),
            config_ver=config_ver,
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
        )

    def get_found_log_item(
        self, found_log_msg: str, found_log_idx: int
    ) -> "AddPairArrayEntryLogSearchItem":
        """Return a found log item.

        Args:
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found

        Returns:
            AddPairArrayEntryLogSearchItem containing found message and
                index
        """
        return AddPairArrayEntryLogSearchItem(
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
            config_ver=self.config_ver,
        )

    def run_process(self) -> None:
        """Run the process to handle the log message."""
        split_msg = self.found_log_msg.split()
        cmd_runner = split_msg[1]
        name_0 = split_msg[4][15:-2]  # lose left paren, comma, quotes
        name_1 = split_msg[5][7:-2]  # lose right paren, quotes
        pair_key: st.PairKey = st.PairKey(name_0, name_1)
        self.config_ver.handle_add_pair_array_log_msg(
            cmd_runner=cmd_runner, pair_key=pair_key, log_msg=self.found_log_msg
        )


########################################################################
# AddStatusBlockEntryLogSearchItem
########################################################################
class AddStatusBlockEntryLogSearchItem(LogSearchItem):
    """Input to search log msgs."""

    def __init__(
        self,
        config_ver: "ConfigVerifier",
        found_log_msg: str = "",
        found_log_idx: int = 0,
    ) -> None:
        """Initialize the LogItem.

        Args:
            config_ver: configuration verifier
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found
        """
        super().__init__(
            search_str=(
                rf"SmartThread [a-z0-9_]+ \({config_ver.group_name}\) added "
                "status_blocks entry for "
                r"PairKey\(name0='[a-z0-9_]+', name1='[a-z0-9_]+'\), "
                "name = [a-z0-9_]+"
            ),
            config_ver=config_ver,
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
        )

    def get_found_log_item(
        self, found_log_msg: str, found_log_idx: int
    ) -> "AddStatusBlockEntryLogSearchItem":
        """Return a found log item.

        Args:
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found

        Returns:
            AddStatusBlockEntryLogSearchItem containing found message
                and index
        """
        return AddStatusBlockEntryLogSearchItem(
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
            config_ver=self.config_ver,
        )

    def run_process(self) -> None:
        """Run the process to handle the log message."""
        split_msg = self.found_log_msg.split()
        cmd_runner = split_msg[1]
        name_0 = split_msg[7][15:-2]  # lose left paren, comma, quotes
        name_1 = split_msg[8][7:-3]  # lose right paren, quotes
        target = split_msg[11]
        pair_key: st.PairKey = st.PairKey(name_0, name_1)
        self.config_ver.handle_add_status_block_log_msg(
            cmd_runner=cmd_runner,
            pair_key=pair_key,
            target=target,
            log_msg=self.found_log_msg,
        )


########################################################################
# UpdatePairArrayUtcLogSearchItem
########################################################################
class UpdatePairArrayUtcLogSearchItem(LogSearchItem):
    """Input to search log msgs."""

    def __init__(
        self,
        config_ver: "ConfigVerifier",
        found_log_msg: str = "",
        found_log_idx: int = 0,
    ) -> None:
        """Initialize the LogItem.

        Args:
            config_ver: configuration verifier
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found
        """
        super().__init__(
            search_str=(
                rf"SmartThread [a-z0-9_]+ \({config_ver.group_name}\) updated "
                f"_pair_array at UTC {time_match}"
            ),
            config_ver=config_ver,
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
        )

    def get_found_log_item(
        self, found_log_msg: str, found_log_idx: int
    ) -> "UpdatePairArrayUtcLogSearchItem":
        """Return a found log item.

        Args:
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found

        Returns:
            UpdatePairArrayUtcLogSearchItem containing found message
                and index
        """
        return UpdatePairArrayUtcLogSearchItem(
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
            config_ver=self.config_ver,
        )

    def run_process(self) -> None:
        """Run the process to handle the log message."""
        cmd_runner = self.found_log_msg.split()[1]

        pe = self.config_ver.pending_events[cmd_runner]
        if pe[PE.update_pair_array_utc_msg] <= 0:
            raise UnexpectedEvent(
                "UpdatePairArrayUtcLogSearchItem encountered unexpected "
                f"log message: {self.found_log_msg}"
            )

        pe[PE.update_pair_array_utc_msg] -= 1
        self.config_ver.log_test_msg(
            f"UpdatePairArrayUtcLogSearchItem for {cmd_runner=} "
            f"decremented {pe[PE.update_pair_array_utc_msg]=}"
        )

        self.config_ver.add_log_msg(re.escape(self.found_log_msg))


########################################################################
# RegistryStatusLogSearchItem
########################################################################
class RegistryStatusLogSearchItem(LogSearchItem):
    """Input to search log msgs."""

    def __init__(
        self,
        config_ver: "ConfigVerifier",
        found_log_msg: str = "",
        found_log_idx: int = 0,
    ) -> None:
        """Initialize the LogItem.

        Args:
            config_ver: configuration verifier
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found
        """
        super().__init__(
            search_str=(
                rf"name=[a-z0-9_]+ \({config_ver.group_name}\), is_alive=(True|False), "
                f"state={list_of_thread_states}, smart_thread="
            ),
            config_ver=config_ver,
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
        )

    def get_found_log_item(
        self, found_log_msg: str, found_log_idx: int
    ) -> "RegistryStatusLogSearchItem":
        """Return a found log item.

        Args:
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found

        Returns:
            RegistryStatusLogSearchItem containing found message and
                index
        """
        return RegistryStatusLogSearchItem(
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
            config_ver=self.config_ver,
        )

    def run_process(self) -> None:
        """Run the process to handle the log message."""
        split_msg = self.found_log_msg.split()
        target = split_msg[0][5:]
        is_alive = eval(split_msg[2][9:-1])
        state = eval("st." + split_msg[3][6:-1])

        if (
            self.config_ver.pending_events[target][PE.status_msg][(is_alive, state)]
            <= 0
        ):
            if not is_alive and (
                self.config_ver.last_clean_reg_msg_idx
                < self.config_ver.last_thread_stop_msg_idx[target]
            ):
                if (
                    self.config_ver.pending_events[target][PE.status_msg][
                        (True, st.ThreadState.Alive)
                    ]
                    <= 0
                ):
                    raise UnexpectedEvent(
                        f"RegistryStatusLogSearchItem 1 using "
                        f"{(True, st.ThreadState.Alive)} encountered "
                        f"unexpected log message: {self.found_log_msg}"
                    )
                else:
                    self.config_ver.pending_events[target][PE.status_msg][
                        (True, st.ThreadState.Alive)
                    ] -= 1
            else:
                raise UnexpectedEvent(
                    f"RegistryStatusLogSearchItem 2 using {(is_alive, state)} "
                    f"encountered unexpected log message: "
                    f"{self.found_log_msg}"
                )

        else:
            self.config_ver.pending_events[target][PE.status_msg][
                (is_alive, state)
            ] -= 1

        self.config_ver.add_log_msg(re.escape(self.found_log_msg))


########################################################################
# RemRegEntryLogSearchItem
########################################################################
class RemRegEntryLogSearchItem(LogSearchItem):
    """Input to search log msgs."""

    def __init__(
        self,
        config_ver: "ConfigVerifier",
        found_log_msg: str = "",
        found_log_idx: int = 0,
    ) -> None:
        """Initialize the LogItem.

        Args:
            config_ver: configuration verifier
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found
        """
        super().__init__(
            search_str=(
                rf"SmartThread [a-z0-9_]+ \({config_ver.group_name}\) removed "
                f"[a-z0-9_]+ from registry for request: {list_of_smart_requests}"
            ),
            config_ver=config_ver,
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
        )

    def get_found_log_item(
        self, found_log_msg: str, found_log_idx: int
    ) -> "RemRegEntryLogSearchItem":
        """Return a found log item.

        Args:
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found

        Returns:
            RemRegEntryLogSearchItem containing found message and index
        """
        return RemRegEntryLogSearchItem(
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
            config_ver=self.config_ver,
        )

    def run_process(self) -> None:
        """Run the process to handle the log message."""
        split_msg = self.found_log_msg.split()
        cmd_runner = split_msg[1]
        rem_name = split_msg[4]
        process = split_msg[9]

        self.config_ver.handle_rem_reg_log_msg(
            cmd_runner=cmd_runner,
            rem_name=rem_name,
            process=process,
            log_msg=self.found_log_msg,
        )


########################################################################
# DidCleanRegLogSearchItem
########################################################################
class DidCleanRegLogSearchItem(LogSearchItem):
    """Input to search log msgs."""

    def __init__(
        self,
        config_ver: "ConfigVerifier",
        found_log_msg: str = "",
        found_log_idx: int = 0,
    ) -> None:
        """Initialize the LogItem.

        Args:
            config_ver: configuration verifier
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found
        """
        super().__init__(
            search_str=(
                rf"SmartThread [a-z0-9_]+ \({config_ver.group_name}\) did cleanup of "
                rf"registry at UTC {time_match}, deleted \[('[a-z0-9_]+'|, )+\]"
            ),
            config_ver=config_ver,
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
        )

    def get_found_log_item(
        self, found_log_msg: str, found_log_idx: int
    ) -> "DidCleanRegLogSearchItem":
        """Return a found log item.

        Args:
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found

        Returns:
            DidCleanRegLogSearchItem containing found message and index
        """
        return DidCleanRegLogSearchItem(
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
            config_ver=self.config_ver,
        )

    def run_process(self) -> None:
        """Run the process to handle the log message."""
        split_msg = self.found_log_msg.split()
        cmd_runner = split_msg[1]
        target_msg = self.found_log_msg.split("[")[1].split("]")[0].split(", ")

        targets: list[str] = []
        for item in target_msg:
            targets.append(item[1:-1])

        self.config_ver.handle_did_clean_reg_log_msg(
            cmd_runner=cmd_runner, targets=targets, log_msg=self.found_log_msg
        )


########################################################################
# RemStatusBlockEntryLogSearchItem
########################################################################
class RemStatusBlockEntryLogSearchItem(LogSearchItem):
    """Input to search log msgs."""

    def __init__(
        self,
        config_ver: "ConfigVerifier",
        found_log_msg: str = "",
        found_log_idx: int = 0,
    ) -> None:
        """Initialize the LogItem.

        Args:
            config_ver: configuration verifier
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found
        """
        list_of_extras = (
            "(, with non-empty msg_q"
            "|, with wait event set"
            "|, with sync event set)*"
        )
        super().__init__(
            search_str=(
                rf"SmartThread [a-z0-9_]+ \({config_ver.group_name}\) removed "
                "status_blocks entry "
                r"for PairKey\(name0='[a-z0-9_]+', name1='[a-z0-9_]+'\), "
                f"name = [a-z0-9_]+{list_of_extras}"
            ),
            config_ver=config_ver,
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
        )

    def get_found_log_item(
        self, found_log_msg: str, found_log_idx: int
    ) -> "RemStatusBlockEntryLogSearchItem":
        """Return a found log item.

        Args:
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found

        Returns:
            SyncResumedLogSearchItem containing found message and index
        """
        return RemStatusBlockEntryLogSearchItem(
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
            config_ver=self.config_ver,
        )

    def run_process(self) -> None:
        """Run the process to handle the log message."""
        split_msg = self.found_log_msg.split()
        cmd_runner = split_msg[1]
        name_0 = split_msg[7][15:-2]  # lose left paren, comma, quotes
        name_1 = split_msg[8][7:-3]  # lose right paren, quotes
        rem_name = split_msg[11]

        pair_key: st.PairKey = st.PairKey(name_0, name_1)

        pending_msg = pending_wait = pending_sync = False
        if ", with non-empty msg_q" in self.found_log_msg:
            pending_msg = True
        if ", with wait event set" in self.found_log_msg:
            pending_wait = True
        if ", with sync event set" in self.found_log_msg:
            pending_sync = True

        if pending_msg or pending_wait or pending_sync:
            rem_name = rem_name[0:-1]

        pe = self.config_ver.pending_events[cmd_runner]

        def_del_reasons: DefDelReasons = DefDelReasons(
            pending_request=False,
            pending_msg=pending_msg,
            pending_wait=pending_wait,
            pending_sync=pending_sync,
        )

        rem_sb_key: RemSbKey = (rem_name, pair_key, def_del_reasons)
        # self.config_ver.log_test_msg(
        #     'RemStatusBlockEntryLogSearchItem about to check '
        #     f'{pe[PE.rem_status_block_msg][rem_sb_key]=} for '
        #     f'{cmd_runner=}, {rem_sb_key=}'
        # )
        if pe[PE.rem_status_block_msg][rem_sb_key] <= 0:
            self.config_ver.log_test_msg(
                f"RemStatusBlockEntryLogSearchItem using {rem_sb_key=} "
                "encountered unexpected "
                f"log msg: {self.found_log_msg}, {pe[PE.rem_status_block_msg]=}"
            )
            raise UnexpectedEvent(
                f"RemStatusBlockEntryLogSearchItem using {rem_sb_key=} "
                f"encountered unexpected log msg: {self.found_log_msg}"
            )

        pe[PE.rem_status_block_msg][rem_sb_key] -= 1

        if pe[PE.notify_rem_status_block_msg][rem_sb_key] > 0:
            pe[PE.notify_rem_status_block_msg][rem_sb_key] -= 1

        self.config_ver.add_log_msg(
            re.escape(self.found_log_msg), log_level=logging.DEBUG
        )


########################################################################
# RemStatusBlockEntryDefLogSearchItem
########################################################################
class RemStatusBlockEntryDefLogSearchItem(LogSearchItem):
    """Input to search log msgs."""

    def __init__(
        self,
        config_ver: "ConfigVerifier",
        found_log_msg: str = "",
        found_log_idx: int = 0,
    ) -> None:
        """Initialize the LogItem.

        Args:
            config_ver: configuration verifier
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found
        """
        super().__init__(
            search_str=(
                rf"SmartThread [a-z0-9_]+ \({config_ver.group_name}\) removal deferred "
                r"for status_blocks entry for PairKey\(name0='[a-z0-9_]+', "
                r"name1='[a-z0-9_]+'\), name = [a-z0-9_]+, reasons: "
            ),
            config_ver=config_ver,
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
        )

    def get_found_log_item(
        self, found_log_msg: str, found_log_idx: int
    ) -> "RemStatusBlockEntryDefLogSearchItem":
        """Return a found log item.

        Args:
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found

        Returns:
            SyncResumedLogSearchItem containing found message and index
        """
        return RemStatusBlockEntryDefLogSearchItem(
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
            config_ver=self.config_ver,
        )

    def run_process(self) -> None:
        """Run the process to handle the log message."""
        split_msg = self.found_log_msg.split()
        cmd_runner = split_msg[1]
        name_0 = split_msg[9][15:-2]  # lose left paren, comma, quotes
        name_1 = split_msg[10][7:-3]  # lose right paren, quotes
        rem_name = split_msg[13][0:-1]

        pair_key: st.PairKey = st.PairKey(name_0, name_1)

        pending_request = pending_msg = pending_wait = pending_sync = False
        idx = -1
        while split_msg[idx] != "reasons:":
            if split_msg[idx] in ("set", "set,"):
                if split_msg[idx - 2] == "sync":
                    pending_sync = True
                    idx -= 3
                elif split_msg[idx - 2] == "wait":
                    pending_wait = True
                    idx -= 3
            elif split_msg[idx] in ("msg_q", "msg_q,"):
                pending_msg = True
                idx -= 2
            elif split_msg[idx] in ("request", "request,"):
                pending_request = True
                idx -= 2

        pe = self.config_ver.pending_events[cmd_runner]
        def_del_reasons: DefDelReasons = DefDelReasons(
            pending_request=pending_request,
            pending_msg=pending_msg,
            pending_wait=pending_wait,
            pending_sync=pending_sync,
        )

        rem_sb_key: RemSbKey = (rem_name, pair_key, def_del_reasons)

        if pe[PE.rem_status_block_def_msg][rem_sb_key] <= 0:
            raise UnexpectedEvent(
                f"RemStatusBlockEntryDefLogSearchItem using {rem_sb_key=} "
                f"encountered unexpected log msg: {self.found_log_msg}"
            )

        pe[PE.rem_status_block_def_msg][rem_sb_key] -= 1

        if pe[PE.notify_rem_status_block_def_msg][rem_sb_key] > 0:
            pe[PE.notify_rem_status_block_def_msg][rem_sb_key] -= 1

        self.config_ver.add_log_msg(
            re.escape(self.found_log_msg), log_level=logging.DEBUG
        )


########################################################################
# RemPairArrayEntryLogSearchItem
########################################################################
class RemPairArrayEntryLogSearchItem(LogSearchItem):
    """Input to search log msgs."""

    def __init__(
        self,
        config_ver: "ConfigVerifier",
        found_log_msg: str = "",
        found_log_idx: int = 0,
    ) -> None:
        """Initialize the LogItem.

        Args:
            config_ver: configuration verifier
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found
        """
        super().__init__(
            search_str=(
                rf"SmartThread [a-z0-9_]+ \({config_ver.group_name}\) removed "
                "_pair_array entry "
                r"for PairKey\(name0='[a-z0-9_]+', name1='[a-z0-9_]+'\)"
            ),
            config_ver=config_ver,
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
        )

    def get_found_log_item(
        self, found_log_msg: str, found_log_idx: int
    ) -> "RemPairArrayEntryLogSearchItem":
        """Return a found log item.

        Args:
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found

        Returns:
            RemPairArrayEntryLogSearchItem containing found message
                and index
        """
        return RemPairArrayEntryLogSearchItem(
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
            config_ver=self.config_ver,
        )

    def run_process(self) -> None:
        """Run the process to handle the log message."""
        split_msg = self.found_log_msg.split()
        cmd_runner = split_msg[1]
        name_0 = split_msg[7][15:-2]  # lose left paren, comma, quotes
        name_1 = split_msg[8][7:-2]  # lose right paren, quotes
        pair_key: st.PairKey = st.PairKey(name_0, name_1)

        pe = self.config_ver.pending_events[cmd_runner]
        rem_pae_key: RemPaeKey = (cmd_runner, pair_key)

        if pe[PE.rem_pair_array_entry_msg][rem_pae_key] <= 0:
            raise UnexpectedEvent(
                f"RemPairArrayEntryLogSearchItem using {rem_pae_key=}"
                "encountered unexpected "
                f"log message: {self.found_log_msg}"
            )

        pe[PE.rem_pair_array_entry_msg][rem_pae_key] -= 1

        self.config_ver.add_log_msg(re.escape(self.found_log_msg))


########################################################################
# DidCleanPairArrayUtcLogSearchItem
########################################################################
class DidCleanPairArrayUtcLogSearchItem(LogSearchItem):
    """Input to search log msgs."""

    def __init__(
        self,
        config_ver: "ConfigVerifier",
        found_log_msg: str = "",
        found_log_idx: int = 0,
    ) -> None:
        """Initialize the LogItem.

        Args:
            config_ver: configuration verifier
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found
        """
        super().__init__(
            search_str=(
                rf"SmartThread [a-z0-9_]+ \({config_ver.group_name}\) did cleanup of "
                f"_pair_array at UTC {time_match}"
            ),
            config_ver=config_ver,
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
        )

    def get_found_log_item(
        self, found_log_msg: str, found_log_idx: int
    ) -> "DidCleanPairArrayUtcLogSearchItem":
        """Return a found log item.

        Args:
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found

        Returns:
            DidCleanPairArrayUtcLogSearchItem containing found message
                and index
        """
        return DidCleanPairArrayUtcLogSearchItem(
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
            config_ver=self.config_ver,
        )

    def run_process(self) -> None:
        """Run the process to handle the log message."""
        cmd_runner = self.found_log_msg.split()[1]

        pe = self.config_ver.pending_events[cmd_runner]
        if pe[PE.did_cleanup_pair_array_utc_msg] <= 0:
            raise UnexpectedEvent(
                "DidCleanPairArrayUtcLogSearchItem encountered unexpected "
                f"log message: {self.found_log_msg}"
            )

        pe[PE.did_cleanup_pair_array_utc_msg] -= 1

        self.config_ver.add_log_msg(re.escape(self.found_log_msg))


########################################################################
# RequestAckLogSearchItem
########################################################################
class RequestAckLogSearchItem(LogSearchItem):
    """Input to search log msgs."""

    def __init__(
        self,
        config_ver: "ConfigVerifier",
        found_log_msg: str = "",
        found_log_idx: int = 0,
    ) -> None:
        """Initialize the LogItem.

        Args:
            config_ver: configuration verifier
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found
        """
        list_of_acks = (
            "(smart_send sent message to"
            "|smart_recv received [0-9]+ msg[s]* from"
            "|smart_wait resumed by"
            "|smart_resume resumed"
            "|smart_sync set flag for"
            "|smart_sync backout reset local sync_flag for"
            "|smart_sync backout reset remote sync_flag for"
            "|smart_sync achieved with)"
        )
        super().__init__(
            search_str=(
                rf"SmartThread [a-z0-9_]+ \({config_ver.group_name}\) {list_of_acks} "
                "[a-z0-9_]+"
            ),
            config_ver=config_ver,
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
        )

    def get_found_log_item(
        self, found_log_msg: str, found_log_idx: int
    ) -> "RequestAckLogSearchItem":
        """Return a found log item.

        Args:
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found

        Returns:
            SyncResumedLogSearchItem containing found message and index
        """
        return RequestAckLogSearchItem(
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
            config_ver=self.config_ver,
        )

    def run_process(self) -> None:
        """Run the process to handle the log message."""
        split_msg = self.found_log_msg.split()
        cmd_runner = split_msg[1]
        request = split_msg[3]
        action = split_msg[4]
        remote = split_msg[-1]

        pe = self.config_ver.pending_events[cmd_runner]

        ack_key: AckKey = (remote, request)

        if request == "smart_send":
            self.config_ver.set_msg_pending_count(
                receiver=remote, sender=cmd_runner, pending_msg_adj=1
            )
        elif request == "smart_recv":
            self.config_ver.set_msg_pending_count(
                receiver=cmd_runner, sender=remote, pending_msg_adj=0
            )
        elif request == "smart_wait":
            self.config_ver.set_wait_pending_flag(
                waiter=cmd_runner, resumer=remote, pending_wait_flag=False
            )
        elif request == "smart_resume":
            self.config_ver.set_wait_pending_flag(
                waiter=remote, resumer=cmd_runner, pending_wait_flag=True
            )
        elif request == "smart_sync":
            if action == "set":
                ack_key = (remote, "smart_sync_set")
                self.config_ver.set_sync_pending_flag(
                    waiter=remote, resumer=cmd_runner, pending_sync_flag=True
                )
            elif action == "achieved":
                if self.config_ver.auto_sync_ach_or_back_msg:
                    ack_key = (remote, "smart_sync_ach_or_back")
                else:
                    ack_key = (remote, "smart_sync_achieved")
                self.config_ver.set_sync_pending_flag(
                    waiter=cmd_runner, resumer=remote, pending_sync_flag=False
                )
            elif action == "backout":
                if split_msg[6] == "local":
                    if self.config_ver.auto_sync_ach_or_back_msg:
                        ack_key = (remote, "smart_sync_ach_or_back")
                    else:
                        ack_key = (remote, "smart_sync_backout_local")
                    self.config_ver.set_sync_pending_flag(
                        waiter=cmd_runner, resumer=remote, pending_sync_flag=False
                    )
                else:
                    if self.config_ver.auto_sync_ach_or_back_msg:
                        ack_key = (remote, "smart_sync_ach_or_back")
                    else:
                        ack_key = (remote, "smart_sync_backout_remote")
                    self.config_ver.set_sync_pending_flag(
                        waiter=remote, resumer=cmd_runner, pending_sync_flag=False
                    )

        if not (request == "smart_sync" and action == "set"):
            self.config_ver.set_request_pending_flag(
                cmd_runner=cmd_runner, targets={remote}, pending_request_flag=False
            )

        if pe[PE.ack_msg][ack_key] <= 0:
            raise UnexpectedEvent(
                f"RequestAckLogSearchItem using {ack_key=} detected "
                f"unexpected log msg: {self.found_log_msg}"
            )

        pe[PE.ack_msg][ack_key] -= 1

        self.config_ver.add_log_msg(
            re.escape(self.found_log_msg), log_level=logging.INFO
        )


########################################################################
# DetectedStoppedRemoteLogSearchItem
########################################################################
class DetectedStoppedRemoteLogSearchItem(LogSearchItem):
    """Input to search log msgs."""

    def __init__(
        self,
        config_ver: "ConfigVerifier",
        found_log_msg: str = "",
        found_log_idx: int = 0,
    ) -> None:
        """Initialize the LogItem.

        Args:
            config_ver: configuration verifier
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found
        """
        super().__init__(
            search_str=(
                rf"SmartThread [a-z0-9_]+ \({config_ver.group_name}\) "
                f"{list_of_smart_requests} detected remote [a-z0-9_]+ is stopped"
            ),
            config_ver=config_ver,
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
        )

    def get_found_log_item(
        self, found_log_msg: str, found_log_idx: int
    ) -> "DetectedStoppedRemoteLogSearchItem":
        """Return a found log item.

        Args:
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found

        Returns:
            SyncResumedLogSearchItem containing found message and index
        """
        return DetectedStoppedRemoteLogSearchItem(
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
            config_ver=self.config_ver,
        )

    def run_process(self) -> None:
        """Run the process to handle the log message."""
        split_msg = self.found_log_msg.split()
        cmd_runner = split_msg[1]
        remote = split_msg[6]

        self.config_ver.set_request_pending_flag(
            cmd_runner=cmd_runner, targets={remote}, pending_request_flag=False
        )

        self.config_ver.add_log_msg(
            re.escape(self.found_log_msg), log_level=logging.DEBUG
        )


########################################################################
# RequestRefreshLogSearchItem
########################################################################
class RequestRefreshLogSearchItem(LogSearchItem):
    """Input to search log msgs."""

    def __init__(
        self,
        config_ver: "ConfigVerifier",
        found_log_msg: str = "",
        found_log_idx: int = 0,
    ) -> None:
        """Initialize the LogItem.

        Args:
            config_ver: configuration verifier
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found
        """
        super().__init__(
            search_str=(
                rf"SmartThread [a-z0-9_]+ \({config_ver.group_name}\) "
                rf"{list_of_smart_requests} calling refresh, remaining remotes: \["
            ),
            config_ver=config_ver,
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
        )

    def get_found_log_item(
        self, found_log_msg: str, found_log_idx: int
    ) -> "RequestRefreshLogSearchItem":
        """Return a found log item.

        Args:
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found

        Returns:
            SyncResumedLogSearchItem containing found message and index
        """
        return RequestRefreshLogSearchItem(
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
            config_ver=self.config_ver,
        )

    def run_process(self) -> None:
        """Run the process to handle the log message."""
        split_msg = self.found_log_msg.split()
        cmd_runner = split_msg[1]
        request = split_msg[3]
        target_msg = self.found_log_msg.split("[")[1].split("]")[0]

        targets: set[str] = set()
        if target_msg:
            split_targets = target_msg.split()
            for idx in range(0, len(split_targets), 4):
                remote = split_targets[idx + 2][8:-2]
                targets |= {remote}

        self.config_ver.handle_request_refresh_log_msg(
            cmd_runner=cmd_runner,
            request=request,
            targets=targets,
            log_msg=self.found_log_msg,
        )

        self.config_ver.add_log_msg(
            re.escape(self.found_log_msg), log_level=logging.DEBUG
        )


########################################################################
# UnregJoinSuccessLogSearchItem
########################################################################
class UnregJoinSuccessLogSearchItem(LogSearchItem):
    """Input to search log msgs."""

    def __init__(
        self,
        config_ver: "ConfigVerifier",
        found_log_msg: str = "",
        found_log_idx: int = 0,
    ) -> None:
        """Initialize the LogItem.

        Args:
            config_ver: configuration verifier
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found
        """
        super().__init__(
            search_str=(
                rf"SmartThread [a-z0-9_]+ \({config_ver.group_name}\) did successful "
                r"(smart_unreg|smart_join) of \[([a-z0-9_]*|,|'| )*\]"
            ),
            config_ver=config_ver,
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
        )

    def get_found_log_item(
        self, found_log_msg: str, found_log_idx: int
    ) -> "UnregJoinSuccessLogSearchItem":
        """Return a found log item.

        Args:
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found

        Returns:
            SyncResumedLogSearchItem containing found message and index
        """
        return UnregJoinSuccessLogSearchItem(
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
            config_ver=self.config_ver,
        )

    def run_process(self) -> None:
        """Run the process to handle the log message."""
        split_msg = self.found_log_msg.split()
        cmd_runner = split_msg[1]
        request = split_msg[5]
        target_msg = self.found_log_msg.split("[")[1].split("]")[0].split(", ")

        targets: list[str] = []
        for item in target_msg:
            targets.append(item[1:-1])

        pe = self.config_ver.pending_events[cmd_runner]

        uj_key: UnregJoinSuccessKey = (request, targets[0])

        if pe[PE.unreg_join_success_msg][uj_key] <= 0:
            raise UnexpectedEvent(
                f"UnregJoinSuccessLogSearchItem using {uj_key=} detected "
                f"unexpected log msg: {self.found_log_msg}"
            )

        pe[PE.unreg_join_success_msg][uj_key] -= 1

        self.config_ver.add_log_msg(
            re.escape(self.found_log_msg), log_level=logging.INFO
        )


########################################################################
# JoinWaitingLogSearchItem
########################################################################
class JoinWaitingLogSearchItem(LogSearchItem):
    """Input to search log msgs."""

    def __init__(
        self,
        config_ver: "ConfigVerifier",
        found_log_msg: str = "",
        found_log_idx: int = 0,
    ) -> None:
        """Initialize the LogItem.

        Args:
            config_ver: configuration verifier
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found
        """
        super().__init__(
            search_str=(
                rf"SmartThread [a-z0-9_]+ \({config_ver.group_name}\) smart_join "
                r"completed targets: \[('[a-z0-9_]+'|, )*\], "
                r"pending targets: \[('[a-z0-9_]+'|, )*\]"
            ),
            config_ver=config_ver,
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
        )

    def get_found_log_item(
        self, found_log_msg: str, found_log_idx: int
    ) -> "JoinWaitingLogSearchItem":
        """Return a found log item.

        Args:
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found

        Returns:
            SyncResumedLogSearchItem containing found message and index
        """
        return JoinWaitingLogSearchItem(
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
            config_ver=self.config_ver,
        )

    def run_process(self) -> None:
        """Run the process to handle the log message."""
        split_msg = self.found_log_msg.split()
        cmd_runner = split_msg[1]
        left_bracket_split_msg = self.found_log_msg.split("[")
        comp_targ_msg = left_bracket_split_msg[1].split("]")[0].split(", ")

        comp_targets: list[str] = []
        for item in comp_targ_msg:
            comp_targets.append(item[1:-1])

        pend_targets: list[str] = []
        if left_bracket_split_msg[2] != "]":
            pend_targ_msg = left_bracket_split_msg[2].split("]")[0].split(", ")
            for item in pend_targ_msg:
                pend_targets.append(item[1:-1])

        pe = self.config_ver.pending_events[cmd_runner]

        prog_key: JoinProgKey = (len(comp_targets), len(pend_targets))

        if pe[PE.join_progress_msg][prog_key] <= 0:
            raise UnexpectedEvent(
                f"JoinWaitingLogSearchItem using {prog_key=} detected "
                f"unexpected log msg: {self.found_log_msg}"
            )

        pe[PE.join_progress_msg][prog_key] -= 1

        self.config_ver.add_log_msg(
            re.escape(self.found_log_msg), log_level=logging.INFO
        )


########################################################################
# StoppedLogSearchItem
########################################################################
class StoppedLogSearchItem(LogSearchItem):
    """Input to search log msgs."""

    def __init__(
        self,
        config_ver: "ConfigVerifier",
        found_log_msg: str = "",
        found_log_idx: int = 0,
    ) -> None:
        """Initialize the LogItem.

        Args:
            config_ver: configuration verifier
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found
        """
        super().__init__(
            search_str=(
                rf"[a-z0-9_]+ \({config_ver.group_name}\) has been stopped by "
                "[a-z0-9_]+"
            ),
            config_ver=config_ver,
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
        )

    def get_found_log_item(
        self, found_log_msg: str, found_log_idx: int
    ) -> "StoppedLogSearchItem":
        """Return a found log item.

        Args:
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found

        Returns:
            StoppedLogSearchItem containing found message and index
        """
        return StoppedLogSearchItem(
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
            config_ver=self.config_ver,
        )

    def run_process(self) -> None:
        """Run the process to handle the log message."""
        split_msg = self.found_log_msg.split()

        self.config_ver.handle_stopped_log_msg(
            cmd_runner=split_msg[6],
            stopped_name=split_msg[0],
            log_idx=self.found_log_idx,
        )


########################################################################
# CmdWaitingLogSearchItem
########################################################################
class CmdWaitingLogSearchItem(LogSearchItem):
    """Input to search log msgs."""

    def __init__(
        self,
        config_ver: "ConfigVerifier",
        found_log_msg: str = "",
        found_log_idx: int = 0,
    ) -> None:
        """Initialize the LogItem.

        Args:
            config_ver: configuration verifier
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found
        """
        list_of_waiting_methods = (
            "(create_commander_thread"
            "|create_f1_thread"
            "|handle_join"
            "|handle_recv"
            "|handle_recv_tof"
            "|handle_recv_tot"
            "|handle_resume"
            "|handle_start"
            "|handle_sync"
            "|handle_wait"
            "|handle_unregister)"
        )
        super().__init__(
            search_str=(
                rf"cmd_runner='[a-z0-9_]+' \({config_ver.group_name}\) "
                f"{list_of_waiting_methods} waiting for monitor"
            ),
            config_ver=config_ver,
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
        )

    def get_found_log_item(
        self, found_log_msg: str, found_log_idx: int
    ) -> "CmdWaitingLogSearchItem":
        """Return a found log item.

        Args:
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found

        Returns:
            CmdWaitingLogSearchItem containing found message and index
        """
        return CmdWaitingLogSearchItem(
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
            config_ver=self.config_ver,
        )

    def run_process(self) -> None:
        """Run the process to handle the log message."""
        split_msg = self.found_log_msg.split()
        cmd_runner = split_msg[0].split(sep="=")[1]
        cmd_runner = cmd_runner[1:-1]

        self.config_ver.handle_cmd_waiting_log_msg(cmd_runner=cmd_runner)


########################################################################
# DebugLogSearchItem
########################################################################
class DebugLogSearchItem(LogSearchItem):
    """Input to search log msgs."""

    def __init__(
        self,
        config_ver: "ConfigVerifier",
        found_log_msg: str = "",
        found_log_idx: int = 0,
    ) -> None:
        """Initialize the LogItem.

        Args:
            config_ver: configuration verifier
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found
        """
        super().__init__(
            search_str=rf"TestDebug [a-z0-9_]+ \({config_ver.group_name}\)",
            config_ver=config_ver,
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
        )

    def get_found_log_item(
        self, found_log_msg: str, found_log_idx: int
    ) -> "DebugLogSearchItem":
        """Return a found log item.

        Args:
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found

        Returns:
            SyncResumedLogSearchItem containing found message and index
        """
        return DebugLogSearchItem(
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
            config_ver=self.config_ver,
        )

    def run_process(self) -> None:
        """Run the process to handle the log message."""
        log_name = logger.name
        # logger.debug(f"SBT the logger name is {log_name}")
        # split_msg = self.found_log_msg.split()
        # if split_msg[3] == "testcase":
        #     log_name = "test_scottbrian_paratools.test_smart_thread"
        # else:
        #     log_name = "scottbrian_paratools.smart_thread"
        self.config_ver.add_log_msg(
            re.escape(self.found_log_msg),
            log_level=logging.DEBUG,
            log_name=log_name,
        )


########################################################################
# CRunnerRaisesLogSearchItem
########################################################################
class CRunnerRaisesLogSearchItem(LogSearchItem):
    """Input to search log msgs."""

    def __init__(
        self,
        config_ver: "ConfigVerifier",
        found_log_msg: str = "",
        found_log_idx: int = 0,
    ) -> None:
        """Initialize the LogItem.

        Args:
            config_ver: configuration verifier
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found
        """
        list_of_errors = (
            "(SmartThreadRemoteThreadNotAlive"
            "|SmartThreadDeadlockDetected"
            "|SmartThreadRequestTimedOut"
            "|SmartThreadRemoteThreadNotRegistered)"
        )
        super().__init__(
            search_str=(
                rf"SmartThread [a-z0-9_]+ \({config_ver.group_name}\) raising "
                f"{list_of_errors} while processing a {list_of_smart_requests} "
                r"request with targets \[([a-z0-9_]*|,|'| )*\]"
            ),
            config_ver=config_ver,
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
        )

    def get_found_log_item(
        self, found_log_msg: str, found_log_idx: int
    ) -> "CRunnerRaisesLogSearchItem":
        """Return a found log item.

        Args:
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found

        Returns:
            SyncResumedLogSearchItem containing found message and index
        """
        return CRunnerRaisesLogSearchItem(
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
            config_ver=self.config_ver,
        )

    def run_process(self) -> None:
        """Run the process to handle the log message."""
        split_msg = self.found_log_msg.split()
        cmd_runner = split_msg[1]
        target_msg = self.found_log_msg.split("[")[1].split("]")[0].split(", ")

        targets: set[str] = set()
        for item in target_msg:
            targets |= {item[1:-1]}

        self.config_ver.set_request_pending_flag(
            cmd_runner=cmd_runner, targets=targets, pending_request_flag=False
        )

        pe = self.config_ver.pending_events[cmd_runner]
        pe[PE.current_request] = StartRequest(req_type=st.ReqType.NoReq)

        # self.config_ver.add_log_msg(re.escape(self.found_log_msg),
        #                             log_level=logging.ERROR)


########################################################################
# MonitorCheckpointLogSearchItem
########################################################################
class MonitorCheckpointLogSearchItem(LogSearchItem):
    """Input to search log msgs."""

    def __init__(
        self,
        config_ver: "ConfigVerifier",
        found_log_msg: str = "",
        found_log_idx: int = 0,
    ) -> None:
        """Initialize the LogItem.

        Args:
            config_ver: configuration verifier
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found
        """
        super().__init__(
            search_str=f"Monitor Checkpoint: [a-z_]+ {config_ver.group_name} [0-9]+",
            config_ver=config_ver,
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
        )

    def get_found_log_item(
        self, found_log_msg: str, found_log_idx: int
    ) -> "MonitorCheckpointLogSearchItem":
        """Return a found log item.

        Args:
            found_log_msg: log msg that was found
            found_log_idx: index in the log where message was found

        Returns:
            SyncResumedLogSearchItem containing found message and index
        """
        return MonitorCheckpointLogSearchItem(
            found_log_msg=found_log_msg,
            found_log_idx=found_log_idx,
            config_ver=self.config_ver,
        )

    def run_process(self) -> None:
        """Run the process to handle the log message."""
        split_msg = self.found_log_msg.split()
        verify_name = split_msg[2]
        verify_idx = split_msg[4]

        call_stm = f"self.config_ver.{verify_name}(verify_idx={verify_idx})"

        eval(call_stm)

        if verify_name == "verify_config":
            self.config_ver.verify_config_complete_event.set()
        elif verify_name == "check_pending_events":
            self.config_ver.check_pending_events_complete_event.set()


LogSearchItems: TypeAlias = Union[
    RequestEntryExitLogSearchItem,
    SetupCompleteLogSearchItem,
    SubProcessEntryExitLogSearchItem,
    RegistryStatusLogSearchItem,
    AddPairArrayEntryLogSearchItem,
    AddStatusBlockEntryLogSearchItem,
    DidCleanPairArrayUtcLogSearchItem,
    UpdatePairArrayUtcLogSearchItem,
    AddRegEntryLogSearchItem,
    RemRegEntryLogSearchItem,
    RemPairArrayEntryLogSearchItem,
    DidCleanRegLogSearchItem,
    SetStateLogSearchItem,
    InitCompleteLogSearchItem,
    F1AppExitLogSearchItem,
    AlreadyUnregLogSearchItem,
    RequestAckLogSearchItem,
    DetectedStoppedRemoteLogSearchItem,
    RequestRefreshLogSearchItem,
    UnregJoinSuccessLogSearchItem,
    JoinWaitingLogSearchItem,
    StoppedLogSearchItem,
    CmdWaitingLogSearchItem,
    DebugLogSearchItem,
    RemStatusBlockEntryLogSearchItem,
    RemStatusBlockEntryDefLogSearchItem,
    CRunnerRaisesLogSearchItem,
    MonitorCheckpointLogSearchItem,
]


########################################################################
# MockGetTargetState
########################################################################
TargetsDict: TypeAlias = dict[str, dict[str, tuple[st.ThreadState, st.ThreadState]]]
GroupTargetsDict: TypeAlias = dict[str, TargetsDict]


class MockGetTargetState:
    """Tracks targets whose state is to be reported differently."""

    targets: ClassVar[GroupTargetsDict] = {}
    config_ver: ClassVar[dict[str, "ConfigVerifier"]] = {}

    def __init__(self, targets: TargetsDict, config_ver: "ConfigVerifier") -> None:
        """Initialize the mock target_rtn state.

        Args:
            targets: dictionary of targets
            config_ver: instance of ConfigurationVerifier
        """
        MockGetTargetState.targets[config_ver.group_name] = targets
        MockGetTargetState.config_ver[config_ver.group_name] = config_ver

    ####################################################################
    # mock_get_target_state
    ####################################################################
    def mock_get_target_state(self, pk_remote: st.PairKeyRemote) -> st.ThreadState:
        """Get the status of thread that is the target_rtn of a request.

        Args:
            pk_remote: contains target_rtn thread info

        Returns:
            The thread status

        Notes:
            Must be called holding the registry lock either shared or
            exclusive
        """
        group_name: str = self.group_name  # type: ignore
        if pk_remote.remote not in self.registry:  # type: ignore
            if pk_remote.create_time != 0.0:
                ret_state = st.ThreadState.Stopped
            else:
                ret_state = st.ThreadState.Unregistered

        else:
            if (
                not self.registry[pk_remote.remote].thread.is_alive()  # type: ignore
                and self.registry[pk_remote.remote].st_state  # type: ignore
                == st.ThreadState.Alive
            ):
                ret_state = st.ThreadState.Stopped

            elif (
                pk_remote.pair_key in self.pair_array  # type: ignore
                and pk_remote.remote
                in self.pair_array[pk_remote.pair_key].status_blocks  # type: ignore
                and self.pair_array[pk_remote.pair_key]  # type: ignore
                .status_blocks[pk_remote.remote]
                .create_time
                != pk_remote.create_time
            ):
                ret_state = st.ThreadState.Stopped

            elif (
                not self.registry[pk_remote.remote].thread.is_alive()  # type: ignore
                and self.registry[pk_remote.remote].st_state  # type: ignore
                == st.ThreadState.Alive
            ):
                ret_state = st.ThreadState.Stopped

            else:
                ret_state = self.registry[pk_remote.remote].st_state  # type: ignore

        name = self.name  # type: ignore
        if name in MockGetTargetState.targets[group_name]:
            if pk_remote.remote in MockGetTargetState.targets[group_name][name]:
                if (
                    ret_state
                    == MockGetTargetState.targets[group_name][name][pk_remote.remote][0]
                ):
                    old_ret_state = ret_state
                    ret_state = MockGetTargetState.targets[group_name][name][
                        pk_remote.remote
                    ][1]
                    MockGetTargetState.config_ver[group_name].log_test_msg(
                        f"mock {name} ({group_name}) changed state for "
                        f"{pk_remote.remote=} "
                        f"from {old_ret_state=} to {ret_state=}"
                    )

        return ret_state


class MockCleanPairArray:
    """Tracks targets whose state is to be reported differently."""

    # targets: ClassVar[TargetsDict] = {}
    # config_ver: ClassVar["ConfigVerifier"]

    def __init__(self) -> None:
        """Initialize the mock target_rtn state."""
        pass

    ####################################################################
    # mock_clean_pair_arraye
    ####################################################################
    def mock_clean_pair_array(self) -> None:
        """Get status of a thread that is the target_rtn of a request.

        Notes:
            Must be called holding the registry lock either shared or
            exclusive
        """
        pass


@dataclass
class PaLogMsgsFound:
    """Pair array log message info."""

    entered_rpa: bool
    removed_sb_entry: list[st.PairKey]
    removed_pa_entry: list[st.PairKey]
    updated_pa: bool


@dataclass
class StartRequest:
    """StartRequest class used to track command progress."""

    targets: set[str] = field(default_factory=set)
    unreg_remotes: set[str] = field(default_factory=set)
    not_registered_remotes: set[str] = field(default_factory=set)
    timeout_remotes: set[str] = field(default_factory=set)
    stopped_remotes: set[str] = field(default_factory=set)
    deadlock_remotes: set[str] = field(default_factory=set)
    eligible_targets: set[str] = field(default_factory=set)
    completed_targets: set[str] = field(default_factory=set)
    first_round_completed: set[str] = field(default_factory=set)
    stopped_target_threads: set[str] = field(default_factory=set)
    sync_set_ack_remotes: set[str] = field(default_factory=set)
    exp_senders: set[str] = field(default_factory=set)
    exp_resumers: set[str] = field(default_factory=set)
    exp_receivers: set[str] = field(default_factory=set)
    exp_resumed_targets: set[str] = field(default_factory=set)
    timeout_type: TimeoutType = TimeoutType.TimeoutNone
    req_type: st.ReqType = st.ReqType.NoReq


@dataclass
class PendingEvent:
    """Pending event class."""

    start_request: deque[StartRequest]
    current_request: StartRequest
    num_targets_remaining: int
    request_msg: dict[RequestKey, int]
    subprocess_msg: dict[SubProcessKey, int]
    set_state_msg: dict[SetStateKey, int]
    status_msg: dict[tuple[bool, st.ThreadState], int]
    rem_reg_msg: dict[RemRegKey, int]
    did_clean_reg_msg: int
    update_pair_array_utc_msg: int
    did_cleanup_pair_array_utc_msg: int
    rem_reg_targets: deque[list[str]]
    add_reg_msg: dict[AddRegKey, int]
    add_pair_array_msg: dict[AddPaKey, int]
    add_status_block_msg: dict[AddStatusBlockKey, int]
    rem_status_block_msg: dict[RemSbKey, int]
    rem_status_block_def_msg: dict[RemSbKey, int]
    rem_pair_array_entry_msg: dict[RemPaeKey, int]
    notify_rem_status_block_msg: dict[RemSbKey, int]
    notify_rem_status_block_def_msg: dict[RemSbKey, int]
    ack_msg: dict[AckKey, int]


class PE(Enum):
    """PE class used for index into PendingEvent array."""

    start_request = auto()
    current_request = auto()
    save_current_request = auto()
    num_targets_remaining = auto()
    request_msg = auto()
    subprocess_msg = auto()
    set_state_msg = auto()
    status_msg = auto()
    rem_reg_msg = auto()
    did_clean_reg_msg = auto()
    update_pair_array_utc_msg = auto()
    did_cleanup_pair_array_utc_msg = auto()
    rem_reg_targets = auto()
    add_reg_msg = auto()
    add_pair_array_msg = auto()
    add_status_block_msg = auto()
    rem_status_block_msg = auto()
    rem_status_block_def_msg = auto()
    rem_pair_array_entry_msg = auto()
    notify_rem_status_block_msg = auto()
    notify_rem_status_block_def_msg = auto()
    ack_msg = auto()
    confirm_stop_msg = auto()
    already_unreg_msg = auto()
    unreg_join_success_msg = auto()
    join_progress_msg = auto()
    init_comp_msg = auto()
    calling_refresh_msg = auto()
    refresh_pending_needed = auto()


class ConfigVerifier:
    """Class that tracks and verifies the SmartThread configuration."""

    def __init__(
        self,
        group_name: str,
        commander_name: str,
        log_ver: LogVer,
        caplog_to_use: pytest.LogCaptureFixture,
        msgs: Msgs,
        max_msgs: int = 10,
        allow_log_test_msg: bool = True,
    ) -> None:
        """Initialize the ConfigVerifier.

        Args:
            group_name: name of group for this ConfigVerifier
            commander_name: name of the thread running the commands
            log_ver: the log verifier to track and verify log msgs
            caplog_to_use: pytest fixture to capture log messages
            msgs: Msgs class instance used to communicate with threads
            max_msgs: max message for the SmartThread msg_q

        """
        self.specified_args = locals()  # used for __repr__, see below
        self.group_name = group_name
        self.commander_name = commander_name
        self.commander_thread_config_built = False

        self.monitor_thread = threading.Thread(target=self.monitor)
        self.monitor_exit = False

        self.main_driver_unreg: threading.Event = threading.Event()

        self.cmd_suite: deque[ConfigCmd] = deque()
        self.cmd_serial_num: int = 0
        self.completed_cmds: dict[str, list[int]] = defaultdict(list)
        self.f1_process_cmds: dict[str, bool] = {}
        self.thread_names: list[str] = [
            commander_name,
            "beta",
            "charlie",
            "delta",
            "echo",
            "fox",
            "george",
            "henry",
            "ida",
            "jack",
            "king",
            "love",
            "mary",
            "nancy",
            "oscar",
            "peter",
            "queen",
            "roger",
            "sam",
            "tom",
            "uncle",
            "victor",
            "wanda",
            "xander",
        ]
        self.unregistered_names: set[str] = set(self.thread_names)
        self.registered_names: set[str] = set()
        self.active_names: set[str] = set()
        self.thread_target_names: set[str] = set()
        self.stopped_remotes: set[str] = set()
        self.expected_registered: dict[str, ThreadTracker] = {}
        # self.expected_pairs: dict[tuple[str, str],
        #                           dict[str, ThreadPairStatus]] = {}
        self.expected_pairs: dict[st.PairKey, dict[str, ThreadPairStatus]] = {}
        self.log_ver = log_ver
        self.allow_log_test_msg = allow_log_test_msg
        self.caplog_to_use = caplog_to_use
        self.msgs = msgs
        self.ops_lock = threading.RLock()

        self.all_threads: dict[str, st.SmartThread] = {}

        self.max_msgs = max_msgs

        self.expected_num_recv_timeouts: int = 0

        self.test_case_aborted = False

        self.stopped_event_items: dict[str, MonitorEventItem] = {}
        self.cmd_waiting_event_items: dict[str, threading.Event] = {}

        self.stopping_names: list[str] = []

        self.recently_stopped: dict[str, int] = defaultdict(int)

        self.log_start_idx: int = 0
        self.log_search_items: tuple[LogSearchItems, ...] = (
            RequestEntryExitLogSearchItem(config_ver=self),
            SetupCompleteLogSearchItem(config_ver=self),
            SubProcessEntryExitLogSearchItem(config_ver=self),
            RegistryStatusLogSearchItem(config_ver=self),
            AddPairArrayEntryLogSearchItem(config_ver=self),
            AddStatusBlockEntryLogSearchItem(config_ver=self),
            DidCleanPairArrayUtcLogSearchItem(config_ver=self),
            UpdatePairArrayUtcLogSearchItem(config_ver=self),
            AddRegEntryLogSearchItem(config_ver=self),
            RemRegEntryLogSearchItem(config_ver=self),
            RemPairArrayEntryLogSearchItem(config_ver=self),
            DidCleanRegLogSearchItem(config_ver=self),
            SetStateLogSearchItem(config_ver=self),
            InitCompleteLogSearchItem(config_ver=self),
            F1AppExitLogSearchItem(config_ver=self),
            AlreadyUnregLogSearchItem(config_ver=self),
            RequestAckLogSearchItem(config_ver=self),
            DetectedStoppedRemoteLogSearchItem(config_ver=self),
            RequestRefreshLogSearchItem(config_ver=self),
            UnregJoinSuccessLogSearchItem(config_ver=self),
            JoinWaitingLogSearchItem(config_ver=self),
            StoppedLogSearchItem(config_ver=self),
            CmdWaitingLogSearchItem(config_ver=self),
            DebugLogSearchItem(config_ver=self),
            RemStatusBlockEntryLogSearchItem(config_ver=self),
            RemStatusBlockEntryDefLogSearchItem(config_ver=self),
            CRunnerRaisesLogSearchItem(config_ver=self),
            MonitorCheckpointLogSearchItem(config_ver=self),
        )

        self.log_found_items: deque[LogSearchItem] = deque()

        self.pending_events: dict[str, PendEvents] = {}
        self.auto_calling_refresh_msg = True
        self.auto_sync_ach_or_back_msg = True
        self.potential_def_del_pairs: dict[PotentialDefDelKey, int] = defaultdict(int)
        self.setup_pending_events()

        self.snap_shot_data: dict[int, SnapShotDataItem] = {}

        self.last_clean_reg_msg_idx: int = 0
        self.last_thread_stop_msg_idx: dict[str, int] = defaultdict(int)

        self.monitor_event: threading.Event = threading.Event()
        self.monitor_condition: threading.Condition = threading.Condition()
        self.monitor_pause: int = 0
        self.check_pending_events_complete_event: threading.Event = threading.Event()
        self.verify_config_complete_event: threading.Event = threading.Event()
        self.monitor_thread.start()

    ####################################################################
    # __repr__
    ####################################################################
    def __repr__(self) -> str:
        """Return a representation of the class.

        Returns:
            The representation as how the class is instantiated

        """
        if TYPE_CHECKING:
            __class__: Type[ConfigVerifier]  # noqa: F842
        classname = self.__class__.__name__
        parms = ""
        comma = ""

        for key, item in self.specified_args.items():
            if item:  # if not None
                if key in ("log_ver",):
                    if type(item) is str:
                        parms += comma + f"{key}='{item}'"
                    else:
                        parms += comma + f"{key}={item}"
                    comma = ", "  # after first item, now need comma

        return f"{classname}({parms})"

    ####################################################################
    # setup_pending_events
    ####################################################################
    def abort_test_case(self) -> None:
        """Abort the test case."""
        self.log_test_msg(f"aborting test case {get_formatted_call_sequence()}")
        self.test_case_aborted = True
        self.abort_all_f1_threads()

    ####################################################################
    # setup_pending_events
    ####################################################################
    def setup_pending_events(self) -> None:
        """Setup the pending events for all threads."""
        self.pending_events = {}
        for name in self.thread_names:
            self.pending_events[name] = {}
        for name in self.thread_names:
            self.pending_events[name][PE.start_request] = deque()
            self.pending_events[name][PE.current_request] = StartRequest(
                req_type=st.ReqType.NoReq,
                targets=set(),
                unreg_remotes=set(),
                not_registered_remotes=set(),
                timeout_remotes=set(),
                stopped_remotes=set(),
                deadlock_remotes=set(),
                eligible_targets=set(),
                completed_targets=set(),
                first_round_completed=set(),
                stopped_target_threads=set(),
                exp_senders=set(),
                exp_resumers=set(),
            )
            self.pending_events[name][PE.save_current_request] = StartRequest(
                req_type=st.ReqType.NoReq,
                targets=set(),
                unreg_remotes=set(),
                not_registered_remotes=set(),
                timeout_remotes=set(),
                stopped_remotes=set(),
                deadlock_remotes=set(),
                eligible_targets=set(),
                completed_targets=set(),
                first_round_completed=set(),
                stopped_target_threads=set(),
                exp_senders=set(),
                exp_resumers=set(),
            )
            self.pending_events[name][PE.num_targets_remaining] = 0
            self.pending_events[name][PE.request_msg] = defaultdict(int)
            self.pending_events[name][PE.subprocess_msg] = defaultdict(int)
            self.pending_events[name][PE.set_state_msg] = defaultdict(int)
            self.pending_events[name][PE.status_msg] = defaultdict(int)
            self.pending_events[name][PE.rem_reg_msg] = defaultdict(int)
            self.pending_events[name][PE.did_clean_reg_msg] = 0
            self.pending_events[name][PE.update_pair_array_utc_msg] = 0
            self.pending_events[name][PE.did_cleanup_pair_array_utc_msg] = 0
            self.pending_events[name][PE.rem_reg_targets] = deque()
            self.pending_events[name][PE.add_reg_msg] = defaultdict(int)
            self.pending_events[name][PE.add_pair_array_msg] = defaultdict(int)
            self.pending_events[name][PE.add_status_block_msg] = defaultdict(int)
            self.pending_events[name][PE.rem_status_block_msg] = defaultdict(int)
            self.pending_events[name][PE.rem_status_block_def_msg] = defaultdict(int)
            self.pending_events[name][PE.rem_pair_array_entry_msg] = defaultdict(int)
            self.pending_events[name][PE.notify_rem_status_block_msg] = defaultdict(int)
            self.pending_events[name][PE.notify_rem_status_block_def_msg] = defaultdict(
                int
            )
            self.pending_events[name][PE.ack_msg] = defaultdict(int)
            self.pending_events[name][PE.confirm_stop_msg] = defaultdict(int)
            self.pending_events[name][PE.already_unreg_msg] = defaultdict(int)
            self.pending_events[name][PE.unreg_join_success_msg] = defaultdict(int)
            self.pending_events[name][PE.join_progress_msg] = defaultdict(int)
            self.pending_events[name][PE.init_comp_msg] = defaultdict(int)
            self.pending_events[name][PE.calling_refresh_msg] = defaultdict(int)
            self.pending_events[name][PE.refresh_pending_needed] = defaultdict(int)

    ####################################################################
    # monitor
    ####################################################################
    def monitor(self) -> None:
        """Gather log messages and call handlers."""
        self.log_test_msg("monitor entered")

        timeout_value_seconds: float = 120.0
        last_msg_processed_time: float = time.time()
        while True:
            self.monitor_event.wait(timeout=0.25)
            self.monitor_event.clear()

            if self.monitor_pause > 0:
                with self.monitor_condition:
                    self.monitor_condition.notify_all()
                continue

            while self.get_log_msgs():
                while self.log_found_items:
                    found_log_item = self.log_found_items.popleft()

                    # log the log msg being processed but mangle it a
                    # little so we don't find it again and get into a
                    # loop here
                    found_msg = found_log_item.found_log_msg
                    if "TestDebug" not in found_msg:
                        semi_msg = found_msg.replace(" ", ";", 3)
                        self.log_test_msg(f"monitor processing msg: {semi_msg}")

                    try:
                        found_log_item.run_process()
                    except Exception as exc:
                        self.log_test_msg(f"monitor detected exception {exc}")
                        self.abort_test_case()
                        raise

                    last_msg_processed_time = time.time()

            if time.time() - last_msg_processed_time > timeout_value_seconds:
                logger.debug(
                    f"TestDebug {self.commander_name} ({self.group_name}) testcase "
                    "monitor aborting test case"
                )
                self.abort_test_case()
                error_msg = "monitor timed out"
                self.log_test_msg(error_msg)
                raise CmdTimedOut(error_msg)

            if self.monitor_exit:
                break

        self.log_test_msg(f"monitor exiting: {self.monitor_exit=}")

    ####################################################################
    # set_request_pending_flag
    ####################################################################
    def set_request_pending_flag(
        self, cmd_runner: str, targets: set[str], pending_request_flag: bool
    ) -> None:
        """Set or reset request pending flags.

        Args:
            cmd_runner: thread name doing the set or reset
            targets: thread names that are targets of request
            pending_request_flag: specifies value to set for request

        """
        for target in targets:
            pair_key = st.SmartThread._get_pair_key(cmd_runner, target)
            if pair_key not in self.expected_pairs:
                continue

            pae = self.expected_pairs[pair_key]

            cb = pae[cmd_runner]
            pot_key: PotentialDefDelKey = (pair_key, cmd_runner)

            if (
                self.auto_calling_refresh_msg
                and cb.pending_request
                and not pending_request_flag
                and cb.pending_msg_count == 0
                and not cb.pending_wait
                and not cb.pending_sync
                and self.potential_def_del_pairs[pot_key] > 0
            ):
                pe = self.pending_events[cmd_runner]
                req_type = pe[PE.current_request].req_type
                pe[PE.calling_refresh_msg][req_type.value] = 1
                self.potential_def_del_pairs[pot_key] = 0

            self.log_test_msg(
                f"set_request_pending_flag {cmd_runner=}, "
                f"{pair_key=}, {target=}, updating from "
                f"{cb.pending_request=} to "
                f"{pending_request_flag=}"
            )
            cb.pending_request = pending_request_flag

    ####################################################################
    # set_msg_pending_count
    ####################################################################
    def set_msg_pending_count(
        self, receiver: str, sender: str, pending_msg_adj: int
    ) -> None:
        """Set or reset one or more pending flags.

        Args:
            receiver: thread name whose msg count is to be adj
            sender: thread name that sent the msg
            pending_msg_adj: specifies value to add or subtract for msg
                count

        """
        pair_key = st.SmartThread._get_pair_key(receiver, sender)
        if pair_key not in self.expected_pairs:
            raise InvalidConfigurationDetected(
                f"set_msg_pending_count detected that for {receiver=}, "
                f"{sender=}: {pair_key=} is not in the "
                f"{self.expected_pairs=}"
            )

        pae = self.expected_pairs[pair_key]

        if receiver not in pae:
            raise InvalidConfigurationDetected(
                f"set_msg_pending_count detected that for {sender=}, "
                f"{pair_key=}: {receiver=} is not in the {pae=}"
            )

        cb = pae[receiver]
        if pending_msg_adj == 0:
            new_msg_count = 0
        else:
            new_msg_count = cb.pending_msg_count + pending_msg_adj
        self.log_test_msg(
            f"set_msg_pending_count {receiver=}, "
            f"{pair_key=}, {sender=}, updating from "
            f"{cb.pending_msg_count=} to "
            f"{new_msg_count=}"
        )
        cb.pending_msg_count = new_msg_count

    ####################################################################
    # set_wait_pending_flag
    ####################################################################
    def set_wait_pending_flag(
        self, waiter: str, resumer: str, pending_wait_flag: bool
    ) -> None:
        """Set or reset one or more pending flags.

        Args:
            waiter: thread name whose wait flag is to be set
            resumer: thread name that set the wait event
            pending_wait_flag: specifies True or False to set the flag

        """
        pair_key = st.SmartThread._get_pair_key(waiter, resumer)
        if pair_key not in self.expected_pairs:
            raise InvalidConfigurationDetected(
                f"set_wait_pending_flag detected that for {waiter=}, "
                f"{resumer=}: {pair_key=} is not in the "
                f"{self.expected_pairs=}"
            )

        pae = self.expected_pairs[pair_key]

        if waiter not in pae:
            raise InvalidConfigurationDetected(
                f"set_wait_pending_flag detected that for {resumer=}, "
                f"{pair_key=}: {waiter=} is not in the {pae=}"
            )

        cb = pae[waiter]

        before_pending_wait_count = cb.pending_wait_count
        if pending_wait_flag:
            cb.pending_wait_count += 1
        else:
            cb.pending_wait_count -= 1

        after_pending_wait_count = cb.pending_wait_count

        if cb.pending_wait_count == 1:
            new_pending_wait_flag = True
        else:
            new_pending_wait_flag = False

        self.log_test_msg(
            f"set_wait_pending_flag {waiter=}, "
            f"{pair_key=}, {resumer=}, {pending_wait_flag=} "
            f"{before_pending_wait_count=} updating from "
            f"{cb.pending_wait=} to "
            f"{new_pending_wait_flag=}, "
            f"{after_pending_wait_count=}"
        )

        cb.pending_wait = new_pending_wait_flag

    ####################################################################
    # set_sync_pending_flag
    ####################################################################
    def set_sync_pending_flag(
        self, waiter: str, resumer: str, pending_sync_flag: bool
    ) -> None:
        """Set or reset one or more pending flags.

        Args:
            waiter: thread name whose wait flag is to be set
            resumer: thread name that set the wait event
            pending_sync_flag: specifies True or False to set the flag

        """
        pair_key = st.SmartThread._get_pair_key(waiter, resumer)
        if pair_key not in self.expected_pairs:
            raise InvalidConfigurationDetected(
                f"set_sync_pending_flag detected that for {waiter=}, "
                f"{resumer=}: {pair_key=} is not in the "
                f"{self.expected_pairs=}"
            )

        pae = self.expected_pairs[pair_key]

        if waiter not in pae:
            raise InvalidConfigurationDetected(
                f"set_sync_pending_flag detected that for {resumer=}, "
                f"{pair_key=}: {waiter=} is not in the {pae=}"
            )

        cb = pae[waiter]

        self.log_test_msg(
            f"set_sync_pending_flag {waiter=}, "
            f"{pair_key=}, {resumer=}, updating from "
            f"{cb.pending_sync=} to "
            f"{pending_sync_flag=}"
        )
        cb.pending_sync = pending_sync_flag

    ####################################################################
    # abort_all_f1_threads
    ####################################################################
    def abort_all_f1_threads(self) -> None:
        """Abort all threads before raising an error."""
        self.log_test_msg(f"abort_all_f1_threads entry {len(self.all_threads.keys())=}")
        for name, thread in self.all_threads.items():
            if name == self.commander_name:
                continue
            self.log_test_msg(
                f"aborting f1_thread {name}, "
                f"thread.is_alive(): {thread.thread.is_alive()}."
            )
            if thread.thread.is_alive():
                exit_cmd = ExitThread(cmd_runners=name, stopped_by=self.commander_name)
                self.add_cmd_info(exit_cmd)
                self.msgs.queue_msg(name, exit_cmd)

        self.monitor_event.set()

        self.log_test_msg("abort_all_f1_threads exit")

    ####################################################################
    # add_cmd
    ####################################################################
    def add_cmd(self, cmd: ConfigCmd, alt_frame_num: Optional[int] = None) -> int:
        """Add a command to the deque.

        Args:
            cmd: command to add
            alt_frame_num: non-zero indicates to add the line number for
                the specified frame to the cmd object so that it will be
                included with in the log just after the line_num in
                parentheses

        Returns:
            the serial number for the command

        """
        if alt_frame_num is not None:
            alt_frame_num += 2
        serial_num = self.add_cmd_info(
            cmd=cmd, frame_num=2, alt_frame_num=alt_frame_num
        )
        self.cmd_suite.append(cmd)
        return serial_num

    ####################################################################
    # add_cmd_info
    ####################################################################
    def add_cmd_info(
        self,
        cmd: ConfigCmd,
        frame_num: int = 1,
        alt_frame_num: Optional[int] = None,
    ) -> int:
        """Add a command to the deque.

        Args:
            cmd: command to add
            frame_num: how many frames back to go for line number
            alt_frame_num: non-zero indicates to add the line number for
                the specified frame to the cmd object so that it will be
                included with in the log just after the line_num in
                parentheses

        Returns:
            the serial number for the command
        """
        self.cmd_serial_num += 1
        cmd.serial_num = self.cmd_serial_num

        frame = _getframe(frame_num)
        caller_info = get_caller_info(frame)
        cmd.line_num = caller_info.line_num
        del frame
        if alt_frame_num is not None and alt_frame_num > 0:
            frame = _getframe(alt_frame_num)
            caller_info = get_caller_info(frame)
            cmd.alt_line_num = caller_info.line_num
            del frame

        cmd.config_ver = self

        return self.cmd_serial_num

    ####################################################################
    # add_log_msg
    ####################################################################
    def add_log_msg(
        self,
        new_log_msg: str,
        log_level: int = logging.DEBUG,
        fullmatch: bool = True,
        log_name: Optional[str] = None,
    ) -> None:
        """Add log message to log_ver for SmartThread logger.

        Args:
            new_log_msg: msg to add to log_ver
            log_level: the logging severity level to use
            fullmatch: specify whether fullmatch should be done instead
                of match
            log_name: name of log to use for add_msg
        """
        if log_name is None:
            log_name = "scottbrian_paratools.smart_thread"
        self.log_ver.add_msg(
            log_name=log_name,
            log_level=log_level,
            log_msg=new_log_msg,
            fullmatch=fullmatch,
        )

    ####################################################################
    # build_get_names_scenario
    ####################################################################
    def build_get_names_scenario(
        self,
        num_reg: int,
        num_alive: int,
        num_stopped: int,
    ) -> None:
        """Test get_smart_thread_names scenarios.

        Args:
            num_reg: num threads in registered state
            num_alive: num threads in alive state
            num_stopped: num threads in stopped state
        """
        reg_names = get_names("reg_", num_reg)
        alive_names = get_names("alive_", num_alive)
        stopped_names = get_names("stopped_", num_stopped)

        self.create_config(
            reg_names=reg_names,
            active_names=alive_names,
            stopped_names=stopped_names,
        )

        self.add_cmd(
            VerifyGetSmartThreadNames(
                cmd_runners=self.commander_name,
                registered_names=reg_names,
                alive_names=alive_names | {self.commander_name},
                stopped_names=stopped_names,
            )
        )

    ####################################################################
    # build_normal_send_recv_scenario
    ####################################################################
    def build_normal_send_recv_scenario(self, actor_names: list[str]) -> None:
        """Adds cmds to the cmd queue.

        Args:
            actor_names: names of threads that will do the sync

        """
        mid_point = len(actor_names) // 2
        senders = actor_names[0:mid_point]
        receivers = actor_names[mid_point:]

        msgs_to_send = SendRecvMsgs(
            sender_names=senders,
            receiver_names=receivers,
            num_msgs=1,
            text="build_normal_send_recv_scenario",
        )

        send_serial_num = self.add_cmd(
            SendMsg(
                cmd_runners=senders,
                receivers=receivers,
                exp_receivers=receivers,
                msgs_to_send=msgs_to_send,
                msg_idx=0,
                log_msg="normal send recv test",
            )
        )
        self.add_cmd(
            ConfirmResponse(
                cmd_runners=[self.commander_name],
                confirm_cmd="Send",
                confirm_serial_num=send_serial_num,
                confirmers=senders,
            )
        )
        recv_serial_num = self.add_cmd(
            RecvMsg(
                cmd_runners=receivers,
                senders=senders,
                exp_senders=senders,
                exp_msgs=msgs_to_send,
                log_msg="normal send recv test",
            )
        )
        self.add_cmd(
            ConfirmResponse(
                cmd_runners=[self.commander_name],
                confirm_cmd="RecvMsg",
                confirm_serial_num=recv_serial_num,
                confirmers=receivers,
            )
        )

    ####################################################################
    # build_normal_resume_wait_scenario
    ####################################################################
    def build_normal_resume_wait_scenario(self, actor_names: list[str]) -> None:
        """Adds cmds to the cmd queue.

        Args:
            actor_names: names of threads that will do the sync

        """
        mid_point = len(actor_names) // 2
        resumers = actor_names[0:mid_point]
        waiters = actor_names[mid_point:]
        resume_serial_num = self.add_cmd(
            Resume(
                cmd_runners=resumers,
                targets=waiters,
                exp_resumed_targets=waiters,
                stopped_remotes=[],
                log_msg="normal resume wait test",
            )
        )
        self.add_cmd(
            ConfirmResponse(
                cmd_runners=[self.commander_name],
                confirm_cmd="Resume",
                confirm_serial_num=resume_serial_num,
                confirmers=resumers,
            )
        )
        wait_serial_num = self.add_cmd(
            Wait(
                cmd_runners=waiters,
                resumers=resumers,
                exp_resumers=resumers,
                log_msg="normal resume wait test",
            )
        )
        self.add_cmd(
            ConfirmResponse(
                cmd_runners=[self.commander_name],
                confirm_cmd="Wait",
                confirm_serial_num=wait_serial_num,
                confirmers=waiters,
            )
        )

    ####################################################################
    # build_normal_sync_scenario
    ####################################################################
    def build_normal_sync_scenario(self, actor_names: list[str]) -> None:
        """Adds cmds to the cmd queue.

        Args:
            actor_names: names of threads that will do the sync

        """
        sync_serial_num = self.add_cmd(
            Sync(
                cmd_runners=actor_names,
                targets=actor_names,
                sync_set_ack_remotes=actor_names,
                log_msg="normal sync test",
            )
        )
        self.add_cmd(
            ConfirmResponse(
                cmd_runners=[self.commander_name],
                confirm_cmd="Sync",
                confirm_serial_num=sync_serial_num,
                confirmers=list(actor_names),
            )
        )

    ####################################################################
    # build_send_sync_recv_scenario
    ####################################################################
    def build_send_sync_recv_scenario(self, actor_names: list[str]) -> None:
        """Adds cmds to the cmd queue.

        Args:
            actor_names: names of threads that will do the sync

        """
        mid_point = len(actor_names) // 2
        senders = actor_names[0:mid_point]
        receivers = actor_names[mid_point:]

        msgs_to_send = SendRecvMsgs(
            sender_names=senders,
            receiver_names=receivers,
            num_msgs=1,
            text="build_send_sync_recv_scenario",
        )

        send_serial_num = self.add_cmd(
            SendMsg(
                cmd_runners=senders,
                receivers=receivers,
                exp_receivers=receivers,
                msgs_to_send=msgs_to_send,
                msg_idx=0,
                log_msg="send sync recv test",
            )
        )
        self.add_cmd(
            ConfirmResponse(
                cmd_runners=[self.commander_name],
                confirm_cmd="SendMsg",
                confirm_serial_num=send_serial_num,
                confirmers=senders,
            )
        )
        sync_serial_num = self.add_cmd(
            Sync(
                cmd_runners=actor_names,
                targets=actor_names,
                sync_set_ack_remotes=actor_names,
                log_msg="send sync recv test",
            )
        )
        self.add_cmd(
            ConfirmResponse(
                cmd_runners=[self.commander_name],
                confirm_cmd="Sync",
                confirm_serial_num=sync_serial_num,
                confirmers=actor_names,
            )
        )
        recv_serial_num = self.add_cmd(
            RecvMsg(
                cmd_runners=receivers,
                senders=senders,
                exp_senders=senders,
                exp_msgs=msgs_to_send,
                log_msg="send sync recv test",
            )
        )
        self.add_cmd(
            ConfirmResponse(
                cmd_runners=[self.commander_name],
                confirm_cmd="RecvMsg",
                confirm_serial_num=recv_serial_num,
                confirmers=receivers,
            )
        )

    ####################################################################
    # build_resume_sync_wait_scenario
    ####################################################################
    def build_resume_sync_wait_scenario(self, actor_names: list[str]) -> None:
        """Adds cmds to the cmd queue.

        Args:
            actor_names: names of threads that will do the sync

        """
        mid_point = len(actor_names) // 2
        resumers = actor_names[0:mid_point]
        waiters = actor_names[mid_point:]
        resume_serial_num = self.add_cmd(
            Resume(
                cmd_runners=resumers,
                targets=waiters,
                exp_resumed_targets=waiters,
                stopped_remotes=[],
                log_msg="resume sync sync wait test",
            )
        )
        self.add_cmd(
            ConfirmResponse(
                cmd_runners=[self.commander_name],
                confirm_cmd="Resume",
                confirm_serial_num=resume_serial_num,
                confirmers=resumers,
            )
        )
        sync_serial_num = self.add_cmd(
            Sync(
                cmd_runners=actor_names,
                targets=actor_names,
                sync_set_ack_remotes=actor_names,
                log_msg="resume sync sync wait test",
            )
        )
        self.add_cmd(
            ConfirmResponse(
                cmd_runners=[self.commander_name],
                confirm_cmd="Sync",
                confirm_serial_num=sync_serial_num,
                confirmers=actor_names,
            )
        )
        wait_serial_num = self.add_cmd(
            Wait(
                cmd_runners=waiters,
                resumers=resumers,
                exp_resumers=resumers,
                log_msg="resume sync sync wait test",
            )
        )
        self.add_cmd(
            ConfirmResponse(
                cmd_runners=[self.commander_name],
                confirm_cmd="Wait",
                confirm_serial_num=wait_serial_num,
                confirmers=waiters,
            )
        )

    ####################################################################
    # build_recv_deadlock_scenario
    ####################################################################
    def build_recv_deadlock_scenario(self, actor_names: list[str]) -> None:
        """Adds cmds to the cmd queue.

        Args:
            actor_names: names of threads that will do the sync

        """
        mid_point = len(actor_names) // 2
        receivers1 = actor_names[0:mid_point]
        receivers2 = actor_names[mid_point:]

        msgs_to_send = SendRecvMsgs(
            sender_names=receivers1 + receivers2,
            receiver_names=receivers1 + receivers2,
            num_msgs=1,
            text="build_recv_deadlock_scenario",
        )

        recv_serial_num_1 = self.add_cmd(
            RecvMsg(
                cmd_runners=receivers1,
                senders=receivers2,
                exp_senders=set(),
                exp_msgs=msgs_to_send,
                deadlock_remotes=set(receivers2),
                log_msg="receive deadlock test",
            )
        )

        self.add_cmd(
            WaitForRequestTimeouts(
                cmd_runners=self.commander_name,
                actor_names=receivers1,
                timeout_names=receivers2,
            )
        )

        recv_serial_num_2 = self.add_cmd(
            RecvMsgTimeoutTrue(
                cmd_runners=receivers2,
                senders=receivers1,
                exp_senders=set(),
                exp_msgs=msgs_to_send,
                deadlock_remotes=set(receivers1),
                deadlock_or_timeout=True,
                timeout_names=set(receivers1),
                timeout=5,
                log_msg="receive deadlock test",
            )
        )

        self.add_cmd(
            ConfirmResponse(
                cmd_runners=[self.commander_name],
                confirm_cmd="RecvMsg",
                confirm_serial_num=recv_serial_num_1,
                confirmers=receivers1,
            )
        )

        self.add_cmd(
            ConfirmResponse(
                cmd_runners=[self.commander_name],
                confirm_cmd="RecvMsg",
                confirm_serial_num=recv_serial_num_2,
                confirmers=receivers2,
            )
        )

    ####################################################################
    # build_wait_deadlock_scenario
    ####################################################################
    def build_wait_deadlock_scenario(self, actor_names: list[str]) -> None:
        """Adds cmds to the cmd queue.

        Args:
            actor_names: names of threads that will do the sync

        """
        mid_point = len(actor_names) // 2
        waiters1 = actor_names[0:mid_point]
        waiters2 = actor_names[mid_point:]

        wait_serial_num_1 = self.add_cmd(
            Wait(
                cmd_runners=waiters1,
                resumers=waiters2,
                exp_resumers=set(),
                deadlock_remotes=set(waiters2),
                log_msg="wait deadlock test",
            )
        )

        self.add_cmd(
            WaitForRequestTimeouts(
                cmd_runners=self.commander_name,
                actor_names=waiters1,
                timeout_names=waiters2,
            )
        )

        wait_serial_num_2 = self.add_cmd(
            WaitTimeoutTrue(
                cmd_runners=waiters2,
                resumers=waiters1,
                exp_resumers=set(),
                deadlock_remotes=set(waiters1),
                deadlock_or_timeout=True,
                timeout_remotes=set(waiters1),
                timeout=5,
                log_msg="wait deadlock test",
            )
        )

        self.add_cmd(
            ConfirmResponse(
                cmd_runners=[self.commander_name],
                confirm_cmd="Wait",
                confirm_serial_num=wait_serial_num_1,
                confirmers=waiters1,
            )
        )

        self.add_cmd(
            ConfirmResponse(
                cmd_runners=[self.commander_name],
                confirm_cmd="Wait",
                confirm_serial_num=wait_serial_num_2,
                confirmers=waiters2,
            )
        )

    ####################################################################
    # build_sync_deadlock_scenario
    ####################################################################
    def build_sync_deadlock_scenario(self, actor_names: list[str]) -> None:
        """Adds cmds to the cmd queue.

        Args:
            actor_names: names of threads that will do the sync

        """
        mid_point_1 = len(actor_names) // 3
        mid_point_2 = 2 * mid_point_1
        syncers = actor_names[0:mid_point_1]
        receivers = actor_names[mid_point_1:mid_point_2]
        waiters = actor_names[mid_point_2:]

        msgs_to_send = SendRecvMsgs(
            sender_names=syncers + waiters,
            receiver_names=receivers,
            num_msgs=1,
            text="build_sync_deadlock_scenario",
        )

        sync_serial_num = self.add_cmd(
            Sync(
                cmd_runners=syncers,
                targets=actor_names,
                sync_set_ack_remotes=actor_names,
                deadlock_remotes=receivers + waiters,
                log_msg="sync deadlock test",
            )
        )

        self.add_cmd(
            WaitForRequestTimeouts(
                cmd_runners=self.commander_name,
                actor_names=syncers,
                timeout_names=receivers + waiters,
            )
        )

        recv_serial_num = self.add_cmd(
            RecvMsg(
                cmd_runners=receivers,
                senders=syncers + waiters,
                exp_senders=set(),
                exp_msgs=msgs_to_send,
                deadlock_remotes=syncers + waiters,
                log_msg="sync deadlock test",
            )
        )

        wait_serial_num = self.add_cmd(
            Wait(
                cmd_runners=waiters,
                resumers=syncers,
                exp_resumers=set(),
                deadlock_remotes=syncers + receivers,
                log_msg="sync deadlock test",
            )
        )

        self.add_cmd(
            ConfirmResponse(
                cmd_runners=[self.commander_name],
                confirm_cmd="Sync",
                confirm_serial_num=sync_serial_num,
                confirmers=syncers,
            )
        )

        self.add_cmd(
            ConfirmResponse(
                cmd_runners=[self.commander_name],
                confirm_cmd="RecvMsg",
                confirm_serial_num=recv_serial_num,
                confirmers=receivers,
            )
        )

        self.add_cmd(
            ConfirmResponse(
                cmd_runners=[self.commander_name],
                confirm_cmd="Wait",
                confirm_serial_num=wait_serial_num,
                confirmers=waiters,
            )
        )

    ####################################################################
    # build_deadlock_scenario
    ####################################################################
    def build_deadlock_scenario(
        self, scenario_list: list[DeadlockScenario], num_cd_actors: int
    ) -> None:
        """Build ConfigCmd items for sync scenarios.

        Args:
            scenario_list: scenario 1, 2, and 3
            num_cd_actors: number of syncers, resumers, and waiters

        """
        actions: dict[DeadlockScenario, Callable[..., None]] = {
            DeadlockScenario.NormalSendRecv: self.build_normal_send_recv_scenario,
            DeadlockScenario.NormalResumeWait: self.build_normal_resume_wait_scenario,
            DeadlockScenario.NormalSync: self.build_normal_sync_scenario,
            DeadlockScenario.SendSyncRecv: self.build_send_sync_recv_scenario,
            DeadlockScenario.ResumeSyncWait: self.build_resume_sync_wait_scenario,
            DeadlockScenario.RecvDeadlock: self.build_recv_deadlock_scenario,
            DeadlockScenario.WaitDeadlock: self.build_wait_deadlock_scenario,
            DeadlockScenario.SyncDeadlock: self.build_sync_deadlock_scenario,
        }
        # Make sure we have enough threads
        assert num_cd_actors <= len(self.unregistered_names)

        self.build_config(cmd_runner=self.commander_name, num_active=num_cd_actors + 1)

        active_names_copy = self.active_names - {self.commander_name}

        ################################################################
        # choose actor_names
        ################################################################
        actor_names = self.choose_names(
            name_collection=active_names_copy,
            num_names_needed=num_cd_actors,
            update_collection=True,
            var_name_for_log="actor_names",
        )

        for scenario in scenario_list:
            actions[scenario](actor_names=actor_names)

    ####################################################################
    # create_config
    ####################################################################
    def create_config(
        self,
        unreg_names: Optional[Iterable[str]] = None,
        reg_names: Optional[Iterable[str]] = None,
        active_names: Optional[Iterable[str]] = None,
        stopped_names: Optional[Iterable[str]] = None,
    ) -> None:
        """Add ConfigCmd items to the queue to create a config.

        Args:
            unreg_names: thread names to be in the unreg pool
            reg_names: thread names to be in the registered pool
            active_names: thread names to be in the active pool
            stopped_names: thread names to be in the stopped pool

        """
        self.thread_names = [self.commander_name]
        if unreg_names:
            self.thread_names.extend(unreg_names)

        if reg_names:
            self.thread_names.extend(reg_names)
        if active_names:
            self.thread_names.extend(active_names)
        if stopped_names:
            self.thread_names.extend(stopped_names)

        self.unregistered_names = set(self.thread_names)
        self.setup_pending_events()
        self.unregistered_names -= {self.commander_name}

        if reg_names:
            names: list[str] = sorted(reg_names)
            f1_create_items: list[F1CreateItem] = []
            for idx, name in enumerate(names):
                if idx % 2:
                    app_config = AppConfig.ScriptStyle
                else:
                    app_config = AppConfig.RemoteThreadApp

                f1_create_items.append(
                    F1CreateItem(
                        name=name,
                        auto_start=False,
                        target_rtn=outer_f1,
                        app_config=app_config,
                    )
                )

            self.build_create_suite(
                f1_create_items=f1_create_items, validate_config=True
            )

        if active_names:
            names = sorted(active_names)
            f1_create_items = []
            for idx, name in enumerate(names):
                if idx % 2:
                    app_config = AppConfig.ScriptStyle
                else:
                    app_config = AppConfig.RemoteThreadApp

                f1_create_items.append(
                    F1CreateItem(
                        name=name,
                        auto_start=True,
                        target_rtn=outer_f1,
                        app_config=app_config,
                    )
                )

            self.build_create_suite(
                f1_create_items=f1_create_items, validate_config=True
            )

        if stopped_names:
            names = sorted(stopped_names)
            f1_create_items = []
            for idx, name in enumerate(names):
                if idx % 2:
                    app_config = AppConfig.ScriptStyle
                else:
                    app_config = AppConfig.RemoteThreadApp

                f1_create_items.append(
                    F1CreateItem(
                        name=name,
                        auto_start=True,
                        target_rtn=outer_f1,
                        app_config=app_config,
                    )
                )

            self.build_create_suite(
                f1_create_items=f1_create_items, validate_config=True
            )

            self.build_exit_suite(cmd_runner=self.commander_name, names=names)

        self.log_name_groups()

    ####################################################################
    # build_config_build_suite
    ####################################################################
    def build_config_build_suite(
        self,
        num_registered_1: int,
        num_active_1: int,
        num_stopped_1: int,
        num_registered_2: int,
        num_active_2: int,
        num_stopped_2: int,
    ) -> None:
        """Return a list of ConfigCmd items for config build.

        Args:
            num_registered_1: number of threads to initially build as
                registered
            num_active_1: number of threads to initially build as
                active
            num_stopped_1: number of threads to initially build as
                stopped
            num_registered_2: number of threads to reconfigure as
                registered
            num_active_2: number of threads to reconfigure as active
            num_stopped_2: number of threads to reconfigure as stopped

        """
        self.build_config(
            cmd_runner=self.commander_name,
            num_registered=num_registered_1,
            num_active=num_active_1,
            num_stopped=num_stopped_1,
        )
        self.build_config(
            cmd_runner=self.commander_name,
            num_registered=num_registered_2,
            num_active=num_active_2,
            num_stopped=num_stopped_2,
        )

    ####################################################################
    # build_create_suite
    ####################################################################
    def build_create_suite(
        self,
        cmd_runner: Optional[str] = None,
        f1_create_items: Optional[list[F1CreateItem]] = None,
        validate_config: Optional[bool] = True,
    ) -> None:
        """Return a list of ConfigCmd items for a create.

        Args:
            cmd_runner: name of thread to do the creates
            f1_create_items: contain f1_names to create
            validate_config: indicates whether to do config validation

        """
        if cmd_runner:
            cmd_runner_to_use = cmd_runner
        else:
            cmd_runner_to_use = self.commander_name

        if f1_create_items:
            f1_names: list[str] = []
            f1_auto_start_names: list[str] = []
            f1_auto_items: list[F1CreateItem] = []
            f1_no_start_names: list[str] = []
            f1_no_start_items: list[F1CreateItem] = []
            for f1_create_item in f1_create_items:
                f1_names.append(f1_create_item.name)
                if f1_create_item.auto_start:
                    f1_auto_start_names.append(f1_create_item.name)
                    f1_auto_items.append(f1_create_item)
                else:
                    f1_no_start_names.append(f1_create_item.name)
                    f1_no_start_items.append(f1_create_item)
                if f1_create_item.app_config == AppConfig.ScriptStyle:
                    self.thread_target_names |= {f1_create_item.name}
            if not set(f1_names).issubset(self.unregistered_names):
                raise InvalidInputDetected(
                    f"Input names {f1_names} not a "
                    f"subset of unregistered names "
                    f"{self.unregistered_names}"
                )
            self.unregistered_names -= set(f1_names)
            if f1_auto_items:
                self.add_cmd(
                    CreateF1AutoStart(
                        cmd_runners=cmd_runner_to_use, f1_create_items=f1_auto_items
                    )
                )

                self.active_names |= set(f1_auto_start_names)
            elif f1_no_start_items:
                self.add_cmd(
                    CreateF1NoStart(
                        cmd_runners=cmd_runner_to_use, f1_create_items=f1_no_start_items
                    )
                )
                self.registered_names |= set(f1_no_start_names)

        if self.registered_names:
            self.add_cmd(
                VerifyConfig(
                    cmd_runners=cmd_runner_to_use,
                    verify_type=VerifyType.VerifyRegisteredState,
                    names_to_check=self.registered_names.copy(),
                )
            )

        if self.active_names:
            # self.add_cmd(VerifyActive(
            #     cmd_runners=cmd_runner_to_use,
            #     exp_active_names=list(self.active_names)))
            self.add_cmd(
                VerifyConfig(
                    cmd_runners=cmd_runner_to_use,
                    verify_type=VerifyType.VerifyAliveState,
                    names_to_check=self.active_names.copy(),
                )
            )

        if validate_config:
            self.add_cmd(
                VerifyConfig(
                    cmd_runners=cmd_runner_to_use,
                    verify_type=VerifyType.VerifyStructures,
                )
            )

    ####################################################################
    # build_exit_suite
    ####################################################################
    def build_exit_suite(
        self,
        cmd_runner: str,
        names: Iterable[str],
        validate_config: bool = True,
        reset_ops_count: bool = False,
        send_recv_msgs: Optional[SendRecvMsgs] = None,
    ) -> None:
        """Add ConfigCmd items for an exit.

        Args:
            cmd_runner: name of thread that will do the cmd
            names: names of threads to exit
            validate_config: specifies whether to validate the
                configuration
            reset_ops_count: specifies that the pending_ops_count is to
                be set to zero
            send_recv_msgs: contains messages sent to the names

        """
        names = get_set(names)
        if not names.issubset(self.active_names):
            raise InvalidInputDetected(
                f"Input names {names} not a subset "
                f"of active names {self.active_names}"
            )
        active_names = list(self.active_names - names)

        if names:
            self.add_cmd(
                StopThread(
                    cmd_runners=cmd_runner,
                    stop_names=names,
                    reset_ops_count=reset_ops_count,
                    send_recv_msgs=send_recv_msgs,
                )
            )
            if validate_config:
                self.add_cmd(Pause(cmd_runners=cmd_runner, pause_seconds=0.2))
                self.add_cmd(
                    VerifyConfig(
                        cmd_runners=cmd_runner,
                        verify_type=VerifyType.VerifyNotAlive,
                        names_to_check=names,
                    )
                )

                # if alive_state_names:
                self.add_cmd(
                    VerifyConfig(
                        cmd_runners=cmd_runner,
                        verify_type=VerifyType.VerifyState,
                        names_to_check=names,
                        state_to_check=st.ThreadState.Alive,
                    )
                )
        if active_names and validate_config:
            self.add_cmd(
                VerifyConfig(
                    cmd_runners=cmd_runner,
                    verify_type=VerifyType.VerifyAlive,
                    names_to_check=active_names,
                )
            )
            self.add_cmd(
                VerifyConfig(
                    cmd_runners=cmd_runner,
                    verify_type=VerifyType.VerifyState,
                    names_to_check=active_names,
                    state_to_check=st.ThreadState.Alive,
                )
            )

        if validate_config:
            self.add_cmd(
                VerifyConfig(
                    cmd_runners=cmd_runner, verify_type=VerifyType.VerifyStructures
                )
            )

        self.active_names -= names
        self.stopped_remotes |= names

    ####################################################################
    # build_exit_suite_num
    ####################################################################
    def build_exit_suite_num(self, num_to_exit: int) -> None:
        """Return a list of ConfigCmd items for smart_unreg.

        Args:
            num_to_exit: number of threads to exit

        """
        assert num_to_exit > 0
        if (len(self.active_names) - 1) < num_to_exit:
            raise InvalidInputDetected(
                f"Input num_to_exit {num_to_exit} "
                f"is greater than the number of "
                f"registered threads "
                f"{len(self.active_names)}"
            )

        names: list[str] = list(
            random.sample(
                sorted(self.active_names - {self.commander_name}), num_to_exit
            )
        )

        return self.build_exit_suite(cmd_runner=self.commander_name, names=names)

    ####################################################################
    # build_f1_create_suite_num
    ####################################################################
    def build_f1_create_suite_num(
        self, num_to_create: int, auto_start: bool = True, validate_config: bool = True
    ) -> None:
        """Return a list of ConfigCmd items for a create.

        Args:
            num_to_create: number of f1 threads to create
            auto_start: indicates whether to use auto_start
            validate_config: indicates whether to do config validation

        """
        assert num_to_create > 0
        if len(self.unregistered_names) < num_to_create:
            raise InvalidInputDetected(
                f"Input num_to_create {num_to_create} "
                f"is greater than the number of "
                f"unregistered threads "
                f"{len(self.unregistered_names)}"
            )

        names: list[str] = list(
            random.sample(sorted(self.unregistered_names), num_to_create)
        )
        f1_create_items: list[F1CreateItem] = []
        for idx, name in enumerate(names):
            if idx % 2:
                app_config = AppConfig.ScriptStyle
            else:
                app_config = AppConfig.RemoteThreadApp

            f1_create_items.append(
                F1CreateItem(
                    name=name,
                    auto_start=auto_start,
                    target_rtn=outer_f1,
                    app_config=app_config,
                )
            )

        self.build_create_suite(
            f1_create_items=f1_create_items, validate_config=validate_config
        )

    ####################################################################
    # build_join_suite
    ####################################################################
    def build_join_suite(
        self,
        cmd_runners: Iterable[str],
        join_target_names: Iterable[str],
        validate_config: Optional[bool] = True,
    ) -> None:
        """Return a list of ConfigCmd items for join.

        Args:
            cmd_runners: list of names to do the join
            join_target_names: the threads that are to be joined
            validate_config: specifies whether to validate the config
                after the join is done

        """
        cmd_runners = get_set(cmd_runners)
        join_target_names = get_set(join_target_names)

        if not join_target_names.issubset(self.stopped_remotes):
            raise InvalidInputDetected(
                f"Input {join_target_names} is not a "
                "subset of inactive names "
                f"{self.stopped_remotes}"
            )

        if join_target_names:
            self.add_cmd(Join(cmd_runners=cmd_runners, join_names=join_target_names))

            self.add_cmd(
                VerifyConfig(
                    cmd_runners=cmd_runners,
                    verify_type=VerifyType.VerifyNotInRegistry,
                    names_to_check=join_target_names,
                )
            )

            self.add_cmd(
                VerifyConfig(
                    cmd_runners=cmd_runners,
                    verify_type=VerifyType.VerifyNotPaired,
                    names_to_check=join_target_names,
                )
            )

        if validate_config:
            self.add_cmd(
                VerifyConfig(
                    cmd_runners=cmd_runners, verify_type=VerifyType.VerifyStructures
                )
            )

        self.unregistered_names |= join_target_names
        self.stopped_remotes -= join_target_names

    ####################################################################
    # build_join_suite
    ####################################################################
    def build_join_suite_num(
        self, cmd_runners: Iterable[str], num_to_join: int
    ) -> None:
        """Return a list of ConfigCmd items for join.

        Args:
            cmd_runners: threads running the command
            num_to_join: number of threads to join

        """
        assert num_to_join > 0
        if len(self.stopped_remotes) < num_to_join:
            raise InvalidInputDetected(
                f"Input num_to_join {num_to_join} "
                f"is greater than the number of "
                f"stopped threads "
                f"{len(self.stopped_remotes)}"
            )

        names: list[str] = list(
            random.sample(sorted(self.stopped_remotes), num_to_join)
        )

        self.build_join_suite(cmd_runners=cmd_runners, join_target_names=names)

    ####################################################################
    # build_join_timeout_scenario
    ####################################################################
    def build_join_timeout_scenario(
        self,
        timeout_type: TimeoutType,
        num_active_no_target: int,
        num_no_delay_exit: int,
        num_delay_exit: int,
        num_delay_unreg: int,
        num_no_delay_reg: int,
        num_delay_reg: int,
    ) -> None:
        """Return a list of ConfigCmd items for a create.

        Args:
            timeout_type: specifies TimeoutNone, TimeoutFalse,
                or TimeoutTrue
            num_active_no_target: number of threads that should be
                active and stay active during the join as non-targets
            num_no_delay_exit: number of threads that should be active
                and targeted for join, and then exited immediately to
                allow the join to succeed
            num_delay_exit: number of threads that should be active and
                targeted for join, and then be exited after a short
                delay to allow a TimeoutFalse join to succeed, and a
                long delay to cause a TimeoutTrue join to
                timeout and a TimeoutNone to eventually succeed
            num_delay_unreg: number of threads that should be
                unregistered and targeted for join. These will cause the
                already unregistered log message and will be considered
                as successfully joined in the smart_join completion
                message. They will be eventually started to show that
                they are unaffected by the smart_join once they are
                recognized as already unregistered.
            num_no_delay_reg: number of threads that should be
                registered and targeted for join, and then be
                be immediately started and exited to allow the
                join to succeed
            num_delay_reg: number of threads that should be registered
                and targeted for join, and then be started and exited
                after a short delay to allow a TimeoutFalse join to
                succeed, and a long delay to cause a TimeoutTrue join to
                timeout and a TimeoutNone to eventually succeed

        """
        # Make sure we have enough threads
        assert (
            1
            < (
                num_active_no_target
                + num_no_delay_exit
                + num_delay_exit
                + num_delay_unreg
                + num_no_delay_reg
                + num_delay_reg
            )
            <= len(self.unregistered_names)
        )

        if (
            timeout_type == TimeoutType.TimeoutFalse
            or timeout_type == TimeoutType.TimeoutTrue
        ):
            assert (num_delay_exit + num_delay_reg) > 0

        assert num_active_no_target > 0

        num_registered_needed = num_no_delay_reg + num_delay_reg

        num_active_needed = (
            num_active_no_target + num_no_delay_exit + num_delay_exit + 1
        )

        timeout_time = ((num_no_delay_exit + num_no_delay_reg) * 0.3) + (
            (num_delay_exit + num_delay_reg) * 1.5
        )

        if timeout_type == TimeoutType.TimeoutNone:
            pause_time = 0.5
        elif timeout_type == TimeoutType.TimeoutFalse:
            pause_time = 0.5
            timeout_time += pause_time * 4  # prevent timeout
        else:  # timeout True
            pause_time = timeout_time + 1  # force timeout

        self.build_config(
            cmd_runner=self.commander_name,
            num_registered=num_registered_needed,
            num_active=num_active_needed,
        )

        unregistered_names_copy = self.unregistered_names.copy()
        registered_names_copy = self.registered_names.copy()
        active_names_copy = self.active_names - {self.commander_name}

        ################################################################
        # choose receiver_names
        ################################################################
        active_no_target_names = self.choose_names(
            name_collection=active_names_copy,
            num_names_needed=num_active_no_target,
            update_collection=True,
            var_name_for_log="active_no_target_names",
        )

        ################################################################
        # choose active_no_delay_sender_names
        ################################################################
        no_delay_exit_names = self.choose_names(
            name_collection=active_names_copy,
            num_names_needed=num_no_delay_exit,
            update_collection=True,
            var_name_for_log="no_delay_exit_names",
        )

        ################################################################
        # choose active_delay_sender_names
        ################################################################
        delay_exit_names = self.choose_names(
            name_collection=active_names_copy,
            num_names_needed=num_delay_exit,
            update_collection=True,
            var_name_for_log="delay_exit_names",
        )

        ################################################################
        # choose delay_unreg_names
        ################################################################
        delay_unreg_names = self.choose_names(
            name_collection=unregistered_names_copy,
            num_names_needed=num_delay_unreg,
            update_collection=True,
            var_name_for_log="delay_unreg_names",
        )

        ################################################################
        # choose unreg_sender_names
        ################################################################
        no_delay_reg_names = self.choose_names(
            name_collection=registered_names_copy,
            num_names_needed=num_no_delay_reg,
            update_collection=True,
            var_name_for_log="no_delay_reg_names",
        )

        ################################################################
        # choose reg_sender_names
        ################################################################
        delay_reg_names = self.choose_names(
            name_collection=registered_names_copy,
            num_names_needed=num_delay_reg,
            update_collection=True,
            var_name_for_log="delay_reg_names",
        )

        ################################################################
        # start by doing the recv_msgs, one for each sender
        ################################################################
        all_target_names: list[str] = (
            no_delay_exit_names
            + delay_exit_names
            + delay_unreg_names
            + no_delay_reg_names
            + delay_reg_names
        )

        all_timeout_names: list[str] = delay_exit_names + delay_reg_names

        if len(all_target_names) % 2 == 0:
            log_msg = f"join log test: {get_ptime()}"
        else:
            log_msg = None

        ################################################################
        # start the join
        ################################################################
        if timeout_type == TimeoutType.TimeoutNone:
            confirm_cmd_to_use = "Join"
            join_serial_num = self.add_cmd(
                Join(
                    cmd_runners=active_no_target_names[0],
                    join_names=all_target_names,
                    unreg_names=delay_unreg_names,
                    log_msg=log_msg,
                )
            )
        elif timeout_type == TimeoutType.TimeoutFalse:
            confirm_cmd_to_use = "JoinTimeoutFalse"
            join_serial_num = self.add_cmd(
                JoinTimeoutFalse(
                    cmd_runners=active_no_target_names[0],
                    join_names=all_target_names,
                    unreg_names=delay_unreg_names,
                    timeout=timeout_time,
                    log_msg=log_msg,
                )
            )
        else:  # TimeoutType.TimeoutTrue
            confirm_cmd_to_use = "JoinTimeoutTrue"
            join_serial_num = self.add_cmd(
                JoinTimeoutTrue(
                    cmd_runners=active_no_target_names[0],
                    join_names=all_target_names,
                    unreg_names=delay_unreg_names,
                    timeout=timeout_time,
                    timeout_names=all_timeout_names,
                    log_msg=log_msg,
                )
            )

        ################################################################
        # handle no_delay_exit_names
        ################################################################
        if no_delay_exit_names:
            self.build_exit_suite(
                cmd_runner=self.commander_name,
                names=no_delay_exit_names,
                validate_config=False,
            )

        ################################################################
        # handle no_delay_reg_names
        ################################################################
        if no_delay_reg_names:
            self.build_start_suite(
                start_names=no_delay_reg_names, validate_config=False
            )
            self.build_exit_suite(
                cmd_runner=self.commander_name,
                names=no_delay_reg_names,
                validate_config=False,
            )

        ################################################################
        # make sure smart_join is in loop waiting for timeout names
        ################################################################
        if timeout_type != TimeoutType.TimeoutNone and all_timeout_names:
            self.add_cmd(
                WaitForRequestTimeouts(
                    cmd_runners=self.commander_name,
                    actor_names=active_no_target_names[0],
                    timeout_names=all_timeout_names,
                    use_work_remotes=True,
                    as_subset=True,
                )
            )

        ################################################################
        # pause for short or long delay
        ################################################################
        self.add_cmd(Pause(cmd_runners=self.commander_name, pause_seconds=pause_time))

        ################################################################
        # handle delay_exit_names
        ################################################################
        if delay_exit_names:
            self.build_exit_suite(
                cmd_runner=self.commander_name,
                names=delay_exit_names,
                validate_config=False,
            )

        ################################################################
        # handle delay_reg_names
        ################################################################
        if delay_reg_names:
            self.build_start_suite(start_names=delay_reg_names, validate_config=False)
            self.add_cmd(
                VerifyConfig(
                    cmd_runners=self.commander_name,
                    verify_type=VerifyType.VerifyAliveState,
                    names_to_check=delay_reg_names,
                )
            )

            self.build_exit_suite(
                cmd_runner=self.commander_name,
                names=delay_reg_names,
                validate_config=False,
            )

        ################################################################
        # handle delay_unreg_names
        ################################################################
        if delay_unreg_names:
            f1_create_items: list[F1CreateItem] = []
            for idx, name in enumerate(delay_unreg_names):
                if idx % 2:
                    app_config = AppConfig.ScriptStyle
                else:
                    app_config = AppConfig.RemoteThreadApp

                f1_create_items.append(
                    F1CreateItem(
                        name=name,
                        auto_start=True,
                        target_rtn=outer_f1,
                        app_config=app_config,
                    )
                )

            self.build_create_suite(
                f1_create_items=f1_create_items, validate_config=False
            )
            self.build_exit_suite(
                cmd_runner=self.commander_name,
                names=delay_unreg_names,
                validate_config=False,
            )

        ################################################################
        # finally, confirm the smart_recv is done
        ################################################################
        self.add_cmd(
            ConfirmResponse(
                cmd_runners=self.commander_name,
                confirm_cmd=confirm_cmd_to_use,
                confirm_serial_num=join_serial_num,
                confirmers=active_no_target_names[0],
            )
        )

        if delay_unreg_names:
            self.add_cmd(
                VerifyConfig(
                    cmd_runners=self.commander_name,
                    verify_type=VerifyType.VerifyStoppedState,
                    names_to_check=delay_unreg_names,
                )
            )

    ####################################################################
    # build_msg_suite
    ####################################################################
    def build_msg_suite(self, from_names: list[str], to_names: list[str]) -> None:
        """Return a list of ConfigCmd items for msgs.

        Args:
            from_names: names of threads that send
            to_names: names of threads that receive

        """
        msgs_to_send = SendRecvMsgs(
            sender_names=from_names,
            receiver_names=to_names,
            num_msgs=1,
            text="build_msg_suite",
        )

        self.add_cmd(
            SendMsg(
                cmd_runners=from_names,
                receivers=to_names,
                exp_receivers=to_names,
                msgs_to_send=msgs_to_send,
                msg_idx=0,
            )
        )

        self.add_cmd(
            RecvMsg(
                cmd_runners=to_names,
                senders=from_names,
                exp_senders=from_names,
                exp_msgs=msgs_to_send,
            )
        )

    ####################################################################
    # build_pend_sans_sync_scenario
    ####################################################################
    def build_pend_sans_sync_scenario(
        self,
        request_type: st.ReqType,
        pending_request_tf: bool,
        pending_msg_count: int,
        pending_wait_tf: bool,
    ) -> None:
        """Return a list of ConfigCmd items for a create.

        Args:
            request_type: request type that is to get the pending
                flags set on it
            pending_request_tf: if True, pending_request flag is to be
                set
            pending_msg_count: number of msgs to be placed on the
                pending thread
            pending_wait_tf: if True, pending_wait flag is to be set

        Notes:
            There are two test cases dealing with the pending flags:
            test_pend_sans_sync_scenario:
                this will test combinations for:
                    pending_request: True, False
                    pending_msg: count of 0, 1, 2
                    pending_wait: True, False
                using requests:
                    smart_send
                    smart_recv
                    smart_wait
                    smart_resume

            test_pend_sync_only_scenario:
                this will test combinations for:
                    pending_request: True
                    pending_msg: count of 0, 1, 2
                    pending_wait: True, False
                    pending_sync: True, False
                using requests:
                    smart_sync

            The reason for having two different test cases is that
            pending_sync can only be set with smart_sync, and
            only with pending_request also set.
        """
        self.auto_calling_refresh_msg = False
        pending_names = ["pending_0"]
        remote_names = ["remote_0"]

        locker_names = ["locker_0", "locker_1", "locker_2"]
        lm = LockMgr(config_ver=self, locker_names=locker_names)

        joiner_names = ["joiner_0"]

        active_names: list[str] = (
            pending_names + remote_names + locker_names + joiner_names
        )

        self.create_config(active_names=active_names)

        pend_req_serial_num: int = 0
        join_serial_num: int = 0

        stopped_remotes: Union[str, set[str]] = set()
        exp_senders: Union[str, set[str]] = set()
        exp_resumers: Union[str, set[str]] = set()
        ################################################################
        # verify all flags off
        ################################################################
        exp_pending_flags = PendingFlags()
        self.add_cmd(
            VerifyConfig(
                cmd_runners=self.commander_name,
                verify_type=VerifyType.VerifyPendingFlags,
                names_to_check=pending_names,
                aux_names=remote_names,
                exp_pending_flags=exp_pending_flags,
                obtain_reg_lock=False,
            )
        )

        ################################################################
        # handle pending_msg_count
        ################################################################
        msgs_remote_to_pending = SendRecvMsgs(
            sender_names=remote_names,
            receiver_names=pending_names,
            num_msgs=max(1, pending_msg_count),
            text="build_pend_sans_sync_scenario",
        )

        for idx in range(pending_msg_count):
            send_msg_serial_num = self.add_cmd(
                SendMsg(
                    cmd_runners=remote_names,
                    receivers=pending_names,
                    exp_receivers=pending_names,
                    msgs_to_send=msgs_remote_to_pending,
                    msg_idx=idx,
                    send_type=SendType.ToRemotes,
                )
            )
            self.add_cmd(
                ConfirmResponse(
                    cmd_runners=self.commander_name,
                    confirm_cmd="SendMsg",
                    confirm_serial_num=send_msg_serial_num,
                    confirmers=remote_names,
                )
            )

        exp_pending_flags = PendingFlags(pending_msgs=pending_msg_count)
        self.add_cmd(
            VerifyConfig(
                cmd_runners=self.commander_name,
                verify_type=VerifyType.VerifyPendingFlags,
                names_to_check=pending_names,
                aux_names=remote_names,
                exp_pending_flags=exp_pending_flags,
                obtain_reg_lock=False,
            )
        )

        ################################################################
        # handle pending_wait
        ################################################################
        if pending_wait_tf:
            resume_serial_num = self.add_cmd(
                Resume(
                    cmd_runners=remote_names,
                    targets=pending_names,
                    exp_resumed_targets=pending_names,
                )
            )
            self.add_cmd(
                ConfirmResponse(
                    cmd_runners=self.commander_name,
                    confirm_cmd="Resume",
                    confirm_serial_num=resume_serial_num,
                    confirmers=remote_names,
                )
            )

        exp_pending_flags = PendingFlags(
            pending_msgs=pending_msg_count, pending_wait=pending_wait_tf
        )
        self.add_cmd(
            VerifyConfig(
                cmd_runners=self.commander_name,
                verify_type=VerifyType.VerifyPendingFlags,
                names_to_check=pending_names,
                aux_names=remote_names,
                exp_pending_flags=exp_pending_flags,
                obtain_reg_lock=False,
            )
        )

        if pending_request_tf:
            ############################################################
            # start of by getting lock
            # locks held:
            # before: none
            # after : lock
            ############################################################
            lm.get_lock()

            ############################################################
            # smart_req will get behind lock in
            # _verify_thread_is_current
            # locks held:
            # before: lock
            # after : lock|smart_req
            ############################################################
            if request_type == st.ReqType.Smart_send:
                stopped_remotes = remote_names[0]
                msgs_pending_to_remote = SendRecvMsgs(
                    sender_names=pending_names,
                    receiver_names=remote_names,
                    num_msgs=1,
                    text="build_pend_sans_sync_scenario",
                )
                pend_req_serial_num = self.add_cmd(
                    SendMsg(
                        cmd_runners=pending_names[0],
                        receivers=remote_names[0],
                        exp_receivers=set(),
                        msgs_to_send=msgs_pending_to_remote,
                        msg_idx=0,
                        stopped_remotes=stopped_remotes,
                    )
                )
            elif request_type == st.ReqType.Smart_recv:
                if pending_msg_count == 0:
                    stopped_remotes = remote_names[0]
                else:
                    exp_senders = remote_names[0]
                pend_req_serial_num = self.add_cmd(
                    RecvMsg(
                        cmd_runners=pending_names[0],
                        senders=remote_names[0],
                        exp_msgs=msgs_remote_to_pending,
                        exp_senders=exp_senders,
                        stopped_remotes=stopped_remotes,
                    )
                )
            elif request_type == st.ReqType.Smart_wait:
                if not pending_wait_tf:
                    stopped_remotes = remote_names[0]
                else:
                    exp_resumers = remote_names[0]
                pend_req_serial_num = self.add_cmd(
                    Wait(
                        cmd_runners=pending_names[0],
                        resumers=remote_names[0],
                        exp_resumers=exp_resumers,
                        stopped_remotes=stopped_remotes,
                    )
                )
            elif request_type == st.ReqType.Smart_resume:
                stopped_remotes = remote_names[0]
                pend_req_serial_num = self.add_cmd(
                    Resume(
                        cmd_runners=pending_names[0],
                        targets=remote_names[0],
                        exp_resumed_targets=set(),
                        stopped_remotes=stopped_remotes,
                    )
                )
            else:
                raise InvalidInputDetected(
                    "build_pend_sans_sync_scenario detected invalid "
                    f"input with {request_type=}"
                )

            lm.start_request(pending_names[0])

            pe = self.pending_events[pending_names[0]]
            if request_type == st.ReqType.Smart_recv:
                if not pending_wait_tf:
                    ref_key: CallRefKey = "smart_recv"
                    pe[PE.calling_refresh_msg][ref_key] += 1
            elif request_type == st.ReqType.Smart_wait:
                if pending_msg_count == 0:
                    ref_key = "smart_wait"
                    pe[PE.calling_refresh_msg][ref_key] += 1
            else:
                if pending_msg_count == 0 and not pending_wait_tf:
                    ref_key = request_type.value
                    pe[PE.calling_refresh_msg][ref_key] += 1

            ############################################################
            # release lock to allow smart_req to progress to
            # request_set_up where it waits on the lock
            # locks held:
            # before: lock|smart_req|lock
            # after : lock|smart_req|lock
            ############################################################
            lm.advance_request()

            ############################################################
            # smart_join gets behind lock
            # locks held:
            # before: lock|smart_req|lock
            # after : lock|smart_req|lock|smart_join|lock
            ############################################################
            join_serial_num = self.add_cmd(
                Join(cmd_runners=joiner_names[0], join_names=remote_names[0])
            )
            lm.start_request(joiner_names[0])

            ############################################################
            # release lock to allow smart_req to do request_set_up
            # to get pending_request set, and then wait behind lock_0
            # before going into request loop
            # locks held:
            # before: lock|smart_req|lock|smart_join|lock
            # after : lock|smart_join|lock|smart_req|lock
            ############################################################
            lm.advance_request()

        ################################################################
        # verify results
        ################################################################
        exp_pending_flags = PendingFlags(
            pending_request=pending_request_tf,
            pending_msgs=pending_msg_count,
            pending_wait=pending_wait_tf,
            pending_sync=False,
        )
        self.add_cmd(
            VerifyConfig(
                cmd_runners=self.commander_name,
                verify_type=VerifyType.VerifyPendingFlags,
                names_to_check=pending_names,
                aux_names=remote_names,
                exp_pending_flags=exp_pending_flags,
                obtain_reg_lock=False,
            )
        )

        ################################################################
        # verify config structures
        ################################################################
        self.add_cmd(
            VerifyConfig(
                cmd_runners=self.commander_name,
                verify_type=VerifyType.VerifyStructures,
                obtain_reg_lock=False,
            )
        )

        self.build_exit_suite(
            cmd_runner=self.commander_name, names=remote_names, validate_config=False
        )

        if pending_request_tf:
            ############################################################
            # release lock to allow smart_join to progress to wait for
            # the lock in its process loop
            # locks held:
            # before: lock|smart_join|lock|smart_req|lock
            # after : lock|smart_req|lock|smart_join
            ############################################################
            lm.advance_request(trailing_lock=False)

            ############################################################
            # swap smart_req and joiner to allow joiner to go first
            # locks held:
            # before: lock|smart_req|lock|smart_join
            # after : lock|smart_join|lock|smart_req
            ############################################################
            lm.swap_requestors()

            ############################################################
            # release lock to allow smart_join to remove remotes
            # locks held:
            # before: lock|smart_join|lock|smart_req
            # after : lock|smart_req
            ############################################################
            lm.complete_request()

        else:
            ############################################################
            # do smart_join, no locks to deal with
            ############################################################
            join_serial_num = self.add_cmd(
                Join(cmd_runners=joiner_names[0], join_names=remote_names[0])
            )

        ################################################################
        # verify results
        ################################################################
        exp_pending_flags = PendingFlags(
            pending_request=pending_request_tf,
            pending_msgs=pending_msg_count,
            pending_wait=pending_wait_tf,
            pending_sync=False,
        )

        self.add_cmd(
            VerifyConfig(
                cmd_runners=self.commander_name,
                verify_type=VerifyType.VerifyPendingFlags,
                names_to_check=pending_names,
                aux_names=remote_names,
                exp_pending_flags=exp_pending_flags,
                obtain_reg_lock=False,
            )
        )

        pe = self.pending_events[joiner_names[0]]

        pair_key = st.SmartThread._get_pair_key(pending_names[0], remote_names[0])

        pending_msg_tf: bool = False
        if pending_msg_count > 0:
            pending_msg_tf = True
        if pending_request_tf or pending_msg_tf or pending_wait_tf:
            def_del_reasons: DefDelReasons = DefDelReasons(
                pending_request=pending_request_tf,
                pending_msg=pending_msg_tf,
                pending_wait=pending_wait_tf,
                pending_sync=False,
            )

            rem_sb_key: RemSbKey = (pending_names[0], pair_key, def_del_reasons)

            pe[PE.notify_rem_status_block_def_msg][rem_sb_key] += 1

        if lm.lock_positions:  # if we still hold lock and smart_req
            ############################################################
            # release lock to allow smart_req to complete
            # locks held:
            # before: lock|smart_req
            # after:  None
            ############################################################
            lm.complete_request()

        ################################################################
        # confirm the wait is done
        ################################################################
        if pend_req_serial_num:
            self.add_cmd(
                ConfirmResponse(
                    cmd_runners=self.commander_name,
                    confirm_cmd="Wait",
                    confirm_serial_num=pend_req_serial_num,
                    confirmers=pending_names,
                )
            )

        ################################################################
        # confirm the join is done
        ################################################################
        self.add_cmd(
            ConfirmResponse(
                cmd_runners=self.commander_name,
                confirm_cmd="Unregister",
                confirm_serial_num=join_serial_num,
                confirmers=joiner_names,
            )
        )
        ################################################################
        # verify config structures
        ################################################################
        self.add_cmd(
            VerifyConfig(
                cmd_runners=self.commander_name,
                verify_type=VerifyType.VerifyStructures,
                obtain_reg_lock=False,
            )
        )

    ####################################################################
    # build_pend_sync_only_scenario
    ####################################################################
    def build_pend_sync_only_scenario(
        self, pending_msg_count: int, pending_wait_tf: bool, pending_sync_tf: bool
    ) -> None:
        """Return a list of ConfigCmd items for a create.

        Args:
            pending_msg_count: number of msgs to be placed on the
                pending thread
            pending_wait_tf: if True, pending_wait flag is to be set
            pending_sync_tf: if True, pending_sync flag is to be set

        Notes:
            There are two test cases dealing with the pending flags:
            test_pend_sans_sync_scenario:
                this will test combinations for:
                    pending_request: True, False
                    pending_msg: count of 0, 1, 2
                    pending_wait: True, False
                using requests:
                    smart_send
                    smart_recv
                    smart_wait
                    smart_resume

            test_pend_sync_only_scenario:
                this will test combinations for:
                    pending_request: True
                    pending_msg: count of 0, 1, 2
                    pending_wait: True, False
                    pending_sync: True, False
                using requests:
                    smart_sync

            The reason for having two different test cases is that
            pending_sync can only be set with smart_sync, and
            only with pending_request also set.
        """
        self.auto_calling_refresh_msg = False
        pending_names = ["pending_0"]
        remote_names = ["remote_0"]

        locker_names = ["locker_0", "locker_1", "locker_2", "locker_3", "locker_4"]
        lm = LockMgr(config_ver=self, locker_names=locker_names)

        joiner_names = ["joiner_0"]

        active_names: list[str] = (
            pending_names + remote_names + locker_names + joiner_names
        )

        self.create_config(active_names=active_names)

        ################################################################
        # verify all flags off
        ################################################################
        exp_pending_flags = PendingFlags()
        self.add_cmd(
            VerifyConfig(
                cmd_runners=self.commander_name,
                verify_type=VerifyType.VerifyPendingFlags,
                names_to_check=pending_names,
                aux_names=remote_names,
                exp_pending_flags=exp_pending_flags,
                obtain_reg_lock=False,
            )
        )

        ################################################################
        # handle pending_msg_count
        ################################################################
        msgs_remote_to_pending = SendRecvMsgs(
            sender_names=remote_names,
            receiver_names=pending_names,
            num_msgs=max(1, pending_msg_count),
            text="build_pend_sync_only_scenario",
        )

        for idx in range(pending_msg_count):
            send_msg_serial_num = self.add_cmd(
                SendMsg(
                    cmd_runners=remote_names,
                    receivers=pending_names,
                    exp_receivers=pending_names,
                    msgs_to_send=msgs_remote_to_pending,
                    msg_idx=idx,
                    send_type=SendType.ToRemotes,
                )
            )
            self.add_cmd(
                ConfirmResponse(
                    cmd_runners=self.commander_name,
                    confirm_cmd="SendMsg",
                    confirm_serial_num=send_msg_serial_num,
                    confirmers=remote_names,
                )
            )

        exp_pending_flags = PendingFlags(pending_msgs=pending_msg_count)
        self.add_cmd(
            VerifyConfig(
                cmd_runners=self.commander_name,
                verify_type=VerifyType.VerifyPendingFlags,
                names_to_check=pending_names,
                aux_names=remote_names,
                exp_pending_flags=exp_pending_flags,
                obtain_reg_lock=False,
            )
        )

        ################################################################
        # handle pending_wait
        ################################################################
        if pending_wait_tf:
            resume_serial_num = self.add_cmd(
                Resume(
                    cmd_runners=remote_names,
                    targets=pending_names,
                    exp_resumed_targets=pending_names,
                )
            )
            self.add_cmd(
                ConfirmResponse(
                    cmd_runners=self.commander_name,
                    confirm_cmd="Resume",
                    confirm_serial_num=resume_serial_num,
                    confirmers=remote_names,
                )
            )

        exp_pending_flags = PendingFlags(
            pending_msgs=pending_msg_count, pending_wait=pending_wait_tf
        )
        self.add_cmd(
            VerifyConfig(
                cmd_runners=self.commander_name,
                verify_type=VerifyType.VerifyPendingFlags,
                names_to_check=pending_names,
                aux_names=remote_names,
                exp_pending_flags=exp_pending_flags,
                obtain_reg_lock=False,
            )
        )

        ################################################################
        # start of by getting lock
        # locks held:
        # before: none
        # after : lock
        ################################################################
        lm.get_lock()

        ################################################################
        # pend_sync will get behind lock in _verify_thread_is_current
        # locks held:
        # before: lock
        # after : lock|pend_sync|lovk
        ################################################################
        if pending_sync_tf:
            stopped_remotes: Union[str, set[str]] = set()
            sync_set_ack_remotes: Union[str, set[str]] = remote_names[0]
        else:
            stopped_remotes = remote_names[0]
            sync_set_ack_remotes = set()
        pend_req_serial_num = self.add_cmd(
            Sync(
                cmd_runners=pending_names[0],
                targets=remote_names[0],
                sync_set_ack_remotes=sync_set_ack_remotes,
                stopped_remotes=stopped_remotes,
            )
        )

        lm.start_request(requestor_name=pending_names[0])

        if pending_msg_count == 0 and not pending_wait_tf:
            pe = self.pending_events[pending_names[0]]
            ref_key: CallRefKey = "smart_sync"

            pe[PE.calling_refresh_msg][ref_key] += 1

        ############################################################
        # handle sync case part 1
        ############################################################
        if pending_sync_tf:
            ############################################################
            # remote_sync gets behind lock_1
            # locks held:
            # before: lock|pend_sync|lock
            # after : lock|pend_sync|lock|remote_sync|lock
            ############################################################
            self.add_cmd(
                Sync(
                    cmd_runners=remote_names[0],
                    targets=pending_names[0],
                    sync_set_ack_remotes=pending_names[0],
                    stopped_remotes=set(),
                )
            )
            lm.start_request(requestor_name=remote_names[0])

            ############################################################
            # release lock to get pend_sync to progress to setup
            # behind lock
            # locks held:
            # before: lock|pend_sync|lock|remote_sync|lock
            # after : lock|remote_sync|lock|pend_sync|lock
            ############################################################
            lm.advance_request()

            ############################################################
            # release lock to get remote_sync to progress to setup
            # behind lock
            # locks held:
            # before: lock|remote_sync|lock|pend_sync|lock
            # after : lock|pend_sync|lock|remote_sync|lock
            ############################################################
            lm.advance_request()

            ############################################################
            # release lock to get pend_sync to set its pending_request
            # and then get behind lock just before starting request
            # loop
            # locks held:
            # before: lock|pend_sync|lock|remote_sync|lock
            # after : lock|remote_sync|lock|pend_sync|lock
            ############################################################
            lm.advance_request()

            ############################################################
            # release lock to get remote_sync to set its pending_request
            # and then get behind lock just before starting request loop
            # locks held:
            # before: lock|remote_sync|lock|pend_sync|lock
            # after : lock|pend_sync|lock|remote_sync|lock
            ############################################################
            lm.advance_request()

            ############################################################
            # smart_join gets behind lock
            # locks held:
            # before: lock|pend_sync|lock|remote_sync|lock
            # after : lock|pend_sync|lock|remote_sync|lock|smart_join
            #         |lock
            ############################################################
            join_serial_num = self.add_cmd(
                Join(cmd_runners=joiner_names[0], join_names=remote_names[0])
            )
            lm.start_request(requestor_name=joiner_names[0])

            ############################################################
            # release lock to get pend_sync to set sync flag for
            # remote_sync and then get behind lock (because its sync
            # flag is not yet set by remote_sync)
            # locks held:
            # before: lock|pend_sync|lock|remote_sync|lock|smart_join
            #         |lock
            # after : lock|remote_sync|lock|smart_join|lock|pend_sync
            #         |lock
            ############################################################
            lm.advance_request()

            ############################################################
            # release lock to allow remote_sync to set sync flag for
            # pend_sync and complete the request
            # locks held:
            # before: lock|remote_sync|lock|smart_join|lock|pend_sync
            #         |lock
            # after : lock|smart_join|lock|pend_sync|lock
            ############################################################
            lm.complete_request()

        else:
            ############################################################
            # release lock to allow pend_sync to progress to start of
            # request_set_up behind lock
            # before: lock|pend_sync|lock
            # after : lock|pend_sync|lock
            ############################################################
            lm.advance_request()

            ############################################################
            # smart_join gets behind lock
            # locks held:
            # before: lock|pend_sync|lock
            # after : lock|pend_sync|lock|smart_join|lock
            ############################################################
            join_serial_num = self.add_cmd(
                Join(cmd_runners=joiner_names[0], join_names=remote_names[0])
            )
            lm.start_request(joiner_names[0])

            ############################################################
            # release lock to allow pend_sync to do request_set_up
            # to get pending_request set, and then wait behind lock
            # before going into request loop
            # before: lock|pend_sync|lock|smart_join|lock
            # after : lock|smart_join|lock|pend_sync|lock
            ############################################################
            lm.advance_request()

        ################################################################
        # verify results
        ################################################################
        exp_pending_flags = PendingFlags(
            pending_request=True,
            pending_msgs=pending_msg_count,
            pending_wait=pending_wait_tf,
            pending_sync=pending_sync_tf,
        )
        self.add_cmd(
            VerifyConfig(
                cmd_runners=self.commander_name,
                verify_type=VerifyType.VerifyPendingFlags,
                names_to_check=pending_names,
                aux_names=remote_names,
                exp_pending_flags=exp_pending_flags,
                obtain_reg_lock=False,
            )
        )

        ################################################################
        # verify config structures
        ################################################################
        self.add_cmd(
            VerifyConfig(
                cmd_runners=self.commander_name,
                verify_type=VerifyType.VerifyStructures,
                obtain_reg_lock=False,
            )
        )

        self.build_exit_suite(
            cmd_runner=self.commander_name, names=remote_names, validate_config=False
        )

        ################################################################
        # release lock to allow smart_join to progress to start of loop
        # behind lock
        # before: lock|smart_join|lock|pend_sync|lock
        # after : lock|pend_sync|lock|smart_join
        ################################################################
        lm.advance_request(trailing_lock=False)

        ################################################################
        # before: lock|pend_sync|lock|smart_join
        # action: swap pend_sync and smart_join
        # after : lock|smart_join|lock|pend_sync
        ################################################################
        lm.swap_requestors()

        ############################################################
        # release lock to allow smart_join to remove remote_sync
        # before: lock|smart_join|lock|pend_sync
        # after : lock|pend_sync
        ############################################################
        lm.complete_request()

        ################################################################
        # verify results
        ################################################################
        exp_pending_flags = PendingFlags(
            pending_request=True,
            pending_msgs=pending_msg_count,
            pending_wait=pending_wait_tf,
            pending_sync=pending_sync_tf,
        )
        self.add_cmd(
            VerifyConfig(
                cmd_runners=self.commander_name,
                verify_type=VerifyType.VerifyPendingFlags,
                names_to_check=pending_names,
                aux_names=remote_names,
                exp_pending_flags=exp_pending_flags,
                obtain_reg_lock=False,
            )
        )

        pe = self.pending_events[joiner_names[0]]

        pair_key = st.SmartThread._get_pair_key(pending_names[0], remote_names[0])

        pending_msg_tf: bool = False
        if pending_msg_count > 0:
            pending_msg_tf = True
        def_del_reasons: DefDelReasons = DefDelReasons(
            pending_request=True,
            pending_msg=pending_msg_tf,
            pending_wait=pending_wait_tf,
            pending_sync=pending_sync_tf,
        )

        rem_sb_key: RemSbKey = (pending_names[0], pair_key, def_del_reasons)

        pe[PE.notify_rem_status_block_def_msg][rem_sb_key] += 1

        if lm.lock_positions:  # if we still hold lock_2
            ############################################################
            # release lock to allow pend_sync to complete
            # before: lock|pend_sync
            # after :
            ############################################################
            lm.complete_request()

        ################################################################
        # confirm the pend_sync is done
        ################################################################
        if pend_req_serial_num:
            self.add_cmd(
                ConfirmResponse(
                    cmd_runners=self.commander_name,
                    confirm_cmd="Wait",
                    confirm_serial_num=pend_req_serial_num,
                    confirmers=pending_names,
                )
            )

        ################################################################
        # confirm the join is done
        ################################################################
        self.add_cmd(
            ConfirmResponse(
                cmd_runners=self.commander_name,
                confirm_cmd="Join",
                confirm_serial_num=join_serial_num,
                confirmers=joiner_names,
            )
        )

        ################################################################
        # verify config structures
        ################################################################
        self.add_cmd(
            VerifyConfig(
                cmd_runners=self.commander_name,
                verify_type=VerifyType.VerifyStructures,
                obtain_reg_lock=True,
            )
        )

    ####################################################################
    # build_remove_reasons_scenarios
    ####################################################################
    def build_remove_reasons_scenarios(
        self, pending_msg_count: int, pending_wait_tf: bool, pending_sync_tf: bool
    ) -> None:
        """Return a list of ConfigCmd items for a create.

        Args:
            pending_msg_count: number of msgs to be placed on the
                pending thread
            pending_wait_tf: if True, pending_wait flag is to be set
            pending_sync_tf: if True, pending_sync flag is to be set

        """
        self.auto_calling_refresh_msg = False
        pending_names = ["pending_0"]
        remote_names = ["remote_0"]

        locker_names = ["locker_0", "locker_1", "locker_2", "locker_3", "locker_4"]
        lm = LockMgr(config_ver=self, locker_names=locker_names)

        joiner_names = ["joiner_0"]

        active_names: list[str] = (
            pending_names + remote_names + locker_names + joiner_names
        )

        self.create_config(active_names=active_names)

        pending_name = pending_names[0]
        remote_name = remote_names[0]
        joiner_name = joiner_names[0]

        join_serial_num: int = 0

        ################################################################
        # verify all flags off
        ################################################################
        exp_pending_flags = PendingFlags()
        self.add_cmd(
            VerifyConfig(
                cmd_runners=self.commander_name,
                verify_type=VerifyType.VerifyPendingFlags,
                names_to_check=pending_name,
                aux_names=remote_name,
                exp_pending_flags=exp_pending_flags,
                obtain_reg_lock=False,
            )
        )

        ################################################################
        # handle pending_msg_count
        ################################################################
        msgs_remote_to_pending = SendRecvMsgs(
            sender_names=remote_name,
            receiver_names=pending_name,
            num_msgs=max(1, pending_msg_count),
            text="build_remove_reasons_scenarios",
        )

        for idx in range(pending_msg_count):
            send_msg_serial_num = self.add_cmd(
                SendMsg(
                    cmd_runners=remote_name,
                    receivers=pending_name,
                    exp_receivers=pending_name,
                    msgs_to_send=msgs_remote_to_pending,
                    msg_idx=idx,
                    send_type=SendType.ToRemotes,
                )
            )
            self.add_cmd(
                ConfirmResponse(
                    cmd_runners=self.commander_name,
                    confirm_cmd="SendMsg",
                    confirm_serial_num=send_msg_serial_num,
                    confirmers=remote_name,
                )
            )

        exp_pending_flags = PendingFlags(pending_msgs=pending_msg_count)
        self.add_cmd(
            VerifyConfig(
                cmd_runners=self.commander_name,
                verify_type=VerifyType.VerifyPendingFlags,
                names_to_check=pending_name,
                aux_names=remote_name,
                exp_pending_flags=exp_pending_flags,
                obtain_reg_lock=False,
            )
        )

        ################################################################
        # handle pending_wait
        ################################################################
        if pending_wait_tf:
            resume_serial_num = self.add_cmd(
                Resume(
                    cmd_runners=remote_name,
                    exp_resumed_targets=pending_name,
                    targets=pending_name,
                )
            )
            self.add_cmd(
                ConfirmResponse(
                    cmd_runners=self.commander_name,
                    confirm_cmd="Resume",
                    confirm_serial_num=resume_serial_num,
                    confirmers=remote_name,
                )
            )

        exp_pending_flags = PendingFlags(
            pending_msgs=pending_msg_count, pending_wait=pending_wait_tf
        )
        self.add_cmd(
            VerifyConfig(
                cmd_runners=self.commander_name,
                verify_type=VerifyType.VerifyPendingFlags,
                names_to_check=pending_name,
                aux_names=remote_name,
                exp_pending_flags=exp_pending_flags,
                obtain_reg_lock=False,
            )
        )

        ################################################################
        # handle pending_sync
        ################################################################
        sync_serial_num = 0
        if pending_sync_tf:
            ############################################################
            # start of by getting lock
            # locks held:
            # before: none
            # after : lock
            ############################################################
            lm.get_lock()

            ############################################################
            # remote smart_sync will get behind lock in
            # _verify_thread_is_current
            # locks held:
            # before: lock
            # after : lock|smart_sync|lock
            ############################################################
            sync_serial_num = self.add_cmd(
                Sync(
                    cmd_runners=remote_name,
                    targets=pending_name,
                    sync_set_ack_remotes=set(),
                    stopped_remotes=pending_name,
                )
            )

            lm.start_request(remote_name)

            # Normally, handle_request_smart_sync_entry will set up the
            # ack msg when the target_rtn is not included in the set of
            # stopped_remotes. In this case, we know the sync flag will
            # be set for the pending_name, but we include it in the set
            # of stopped_remotes. So, we need to set up the ack msg
            # here.
            pe = self.pending_events[remote_name]

            ack_key: AckKey = (pending_name, "smart_sync_set")

            pe[PE.ack_msg][ack_key] += 1

            # smart_sync will eventually see that it was delete deferred
            # while it was behind the lock when pending_name was joined.
            # So, we need to indicate that the smart_sync will do a
            # refresh.

            pe = self.pending_events[remote_name]
            ref_key: CallRefKey = "smart_sync"
            pe[PE.calling_refresh_msg][ref_key] += 1

            ############################################################
            # release lock to allow smart_sync to do progress to
            # lock in request_set_up
            # locks held:
            # before: lock|smart_sync|lock
            # after : lock|smart_sync|lock
            ############################################################
            lm.advance_request()

            ############################################################
            # smart_join gets behind lock in _verify_thread_is_current
            # locks held:
            # before: lock|smart_sync|lock
            # after : lock|smart_sync|lock|smart_join|lock
            ############################################################
            join_serial_num = self.add_cmd(
                Join(cmd_runners=joiner_name, join_names=pending_name)
            )
            lm.start_request(joiner_name)

            ############################################################
            # release lock to allow smart_sync to do request_set_up
            # to get pending_request set, and then wait behind lock
            # before going into request loop
            # locks held:
            # before: lock|smart_sync|lock|smart_join|lock
            # after : lock|smart_join|lock|smart_sync|lock
            ############################################################
            lm.advance_request()

            ############################################################
            # release lock to allow smart_join to progress to loop
            # locks held:
            # before: lock|smart_join|lock|smart_sync|lock
            # after : lock|smart_sync|lock|smart_join|lock
            ############################################################
            lm.advance_request()

            ############################################################
            # release lock to allow smart_sync to set the sync flag in
            # pending_name and then get behind lock
            # locks held:
            # before: lock|smart_sync|lock|smart_join|lock
            # after : lock|smart_join|lock|smart_sync
            ############################################################
            lm.advance_request(trailing_lock=False)

            pair_key = st.SmartThread._get_pair_key(remote_name, pending_name)
            check_pend_arg: CheckPendArg = (pending_name, pair_key)
            self.add_cmd(
                WaitForCondition(
                    cmd_runners=self.commander_name,
                    check_rtn=self.check_sync_event_set,
                    check_args=check_pend_arg,
                )
            )

        ################################################################
        # verify the pending flags are as expected before we do the join
        ################################################################
        exp_pending_flags = PendingFlags(
            pending_msgs=pending_msg_count,
            pending_wait=pending_wait_tf,
            pending_sync=pending_sync_tf,
        )
        self.add_cmd(
            VerifyConfig(
                cmd_runners=self.commander_name,
                verify_type=VerifyType.VerifyPendingFlags,
                names_to_check=pending_name,
                aux_names=remote_name,
                exp_pending_flags=exp_pending_flags,
                obtain_reg_lock=False,
            )
        )

        ################################################################
        # verify config structures
        ################################################################
        self.add_cmd(
            VerifyConfig(
                cmd_runners=self.commander_name,
                verify_type=VerifyType.VerifyStructures,
                obtain_reg_lock=False,
            )
        )

        ################################################################
        # remove the pending thread
        ################################################################
        self.build_exit_suite(
            cmd_runner=self.commander_name, names=pending_name, validate_config=False
        )

        if pending_sync_tf:
            ############################################################
            # release lock to allow smart_join to remove remotes
            # locks held:
            # before: lock|smart_join|lock|smart_sync
            # after : lock|smart_sync
            ############################################################
            lm.complete_request()

            ############################################################
            # release lock to allow smart_sync to complete
            # locks held:
            # before: lock|smart_sync
            # after : none
            ############################################################
            lm.complete_request()

            self.add_cmd(
                ConfirmResponse(
                    cmd_runners=self.commander_name,
                    confirm_cmd="Sync",
                    confirm_serial_num=sync_serial_num,
                    confirmers=remote_name,
                )
            )
        else:
            ############################################################
            # do smart_join, no locks to deal with
            ############################################################
            join_serial_num = self.add_cmd(
                Join(cmd_runners=joiner_name, join_names=pending_name)
            )

        pe = self.pending_events[joiner_name]

        pair_key = st.SmartThread._get_pair_key(pending_name, remote_name)

        pending_msg_tf: bool = False
        if pending_msg_count > 0:
            pending_msg_tf = True

        def_del_reasons: DefDelReasons = DefDelReasons(
            pending_request=False,
            pending_msg=pending_msg_tf,
            pending_wait=pending_wait_tf,
            pending_sync=pending_sync_tf,
        )

        rem_sb_key: RemSbKey = (pending_name, pair_key, def_del_reasons)

        pe[PE.notify_rem_status_block_msg][rem_sb_key] += 1

        ################################################################
        # confirm the join is done
        ################################################################
        self.add_cmd(
            ConfirmResponse(
                cmd_runners=self.commander_name,
                confirm_cmd="Join",
                confirm_serial_num=join_serial_num,
                confirmers=joiner_names,
            )
        )

        ################################################################
        # verify config structures
        ################################################################
        self.add_cmd(
            VerifyConfig(
                cmd_runners=self.commander_name,
                verify_type=VerifyType.VerifyStructures,
                obtain_reg_lock=True,
            )
        )

    ####################################################################
    # build_backout_sync_remote_scenario
    ####################################################################
    def build_backout_sync_remote_scenario(self, num_pending: int) -> None:
        """Return a list of ConfigCmd items for sync backout scenario.

        Args:
            num_pending: number of threads that will be backed out

        Notes:
            1) The first pending thread will be stopped to cause the
               backout to happen in the _process_sync method, and any
               additional pending threads will not be stopped and will
               be backed out in the _sync_wait_error_cleanup method

        """
        self.auto_sync_ach_or_back_msg = False

        pending_names = get_names("pending_", num_pending)
        remote_names = ["remote_0"]
        joiner_names = ["joiner_0"]

        active_names: list[str] = list(pending_names) + remote_names + joiner_names

        self.create_config(active_names=active_names)

        pending_name = "pending_0"
        remote_name = remote_names[0]
        joiner_name = joiner_names[0]

        timeout_remotes = pending_names - {pending_name}

        ################################################################
        # verify all flags off
        ################################################################
        exp_pending_flags = PendingFlags()
        self.add_cmd(
            VerifyConfig(
                cmd_runners=self.commander_name,
                verify_type=VerifyType.VerifyPendingFlags,
                names_to_check=pending_names,
                aux_names=remote_name,
                exp_pending_flags=exp_pending_flags,
                obtain_reg_lock=False,
            )
        )

        ################################################################
        # issue the sync to set sync_flag for pending_name
        ################################################################
        sync_serial_num = self.add_cmd(
            Sync(
                cmd_runners=remote_name,
                targets=pending_names,
                timeout_remotes=timeout_remotes,
                sync_set_ack_remotes=pending_names,
                stopped_remotes=pending_name,
            )
        )

        ################################################################
        # wait for the pending_sync flag to be set in mock structures
        ################################################################
        for pending in pending_names:
            pair_key = st.SmartThread._get_pair_key(remote_name, pending)
            check_pend_arg: CheckPendArg = (pending, pair_key)
            self.add_cmd(
                WaitForCondition(
                    cmd_runners=self.commander_name,
                    check_rtn=self.check_sync_event_set,
                    check_args=check_pend_arg,
                )
            )

        ################################################################
        # verify the pending flags are as expected before we do the join
        ################################################################
        exp_pending_flags = PendingFlags(pending_sync=True)
        self.add_cmd(
            VerifyConfig(
                cmd_runners=self.commander_name,
                verify_type=VerifyType.VerifyPendingFlags,
                names_to_check=pending_names,
                aux_names=remote_name,
                exp_pending_flags=exp_pending_flags,
                obtain_reg_lock=False,
            )
        )

        ################################################################
        # verify config structures
        ################################################################
        self.add_cmd(
            VerifyConfig(
                cmd_runners=self.commander_name,
                verify_type=VerifyType.VerifyStructures,
                obtain_reg_lock=False,
            )
        )

        ################################################################
        # remove the pending thread to cause the backout
        ################################################################
        self.build_exit_suite(
            cmd_runner=self.commander_name, names=pending_name, validate_config=False
        )

        pe = self.pending_events[remote_name]

        for pending in pending_names:
            ack_key: AckKey = (pending, "smart_sync_backout_remote")

            pe[PE.ack_msg][ack_key] += 1

        ################################################################
        # confirm the sync is done
        ################################################################
        self.add_cmd(
            ConfirmResponse(
                cmd_runners=self.commander_name,
                confirm_cmd="Sync",
                confirm_serial_num=sync_serial_num,
                confirmers=remote_name,
            )
        )

        ################################################################
        # do smart_join
        ################################################################
        join_serial_num = self.add_cmd(
            Join(cmd_runners=joiner_name, join_names=pending_name)
        )

        pe = self.pending_events[joiner_name]
        # pe = self.pending_events[pending_name]

        pair_key = st.SmartThread._get_pair_key(pending_name, remote_name)

        # we expect no reasons
        def_del_reasons: DefDelReasons = DefDelReasons()

        rem_sb_key: RemSbKey = (pending_name, pair_key, def_del_reasons)

        pe[PE.notify_rem_status_block_msg][rem_sb_key] += 1

        ################################################################
        # confirm the join is done
        ################################################################
        self.add_cmd(
            ConfirmResponse(
                cmd_runners=self.commander_name,
                confirm_cmd="Join",
                confirm_serial_num=join_serial_num,
                confirmers=joiner_names,
            )
        )

        ################################################################
        # verify config structures
        ################################################################
        self.add_cmd(
            VerifyConfig(
                cmd_runners=self.commander_name,
                verify_type=VerifyType.VerifyStructures,
                obtain_reg_lock=True,
            )
        )

    ####################################################################
    # build_backout_sync_local_scenario
    ####################################################################
    def build_backout_sync_local_scenario(self) -> None:
        """Return a list of ConfigCmd items for a create."""
        self.auto_sync_ach_or_back_msg = False

        pending_names = ["pending_0"]
        remote_names = ["remote_0"]

        locker_names = ["locker_0", "locker_1", "locker_2", "locker_3", "locker_4"]
        lm = LockMgr(config_ver=self, locker_names=locker_names)

        active_names: list[str] = pending_names + remote_names + locker_names

        self.create_config(active_names=active_names)

        pending_name = pending_names[0]
        remote_name = remote_names[0]

        timeout_time: IntOrFloat = 2
        pause_time: IntOrFloat = timeout_time * 1.5

        ################################################################
        # verify all flags off
        ################################################################
        exp_pending_flags = PendingFlags()
        self.add_cmd(
            VerifyConfig(
                cmd_runners=self.commander_name,
                verify_type=VerifyType.VerifyPendingFlags,
                names_to_check=pending_name,
                aux_names=remote_name,
                exp_pending_flags=exp_pending_flags,
                obtain_reg_lock=False,
            )
        )

        ################################################################
        # start off by getting lock_0
        # locks held:
        # before: none
        # after : lock_0
        ################################################################
        lm.get_lock()

        ################################################################
        # before: lock
        # remote_sync will get behind lock in _verify_thread_is_current
        # after : lock|remote_sync_vt|lock
        ################################################################
        remote_sync_serial_num = self.add_cmd(
            SyncTimeoutTrue(
                cmd_runners=remote_name,
                targets=pending_name,
                sync_set_ack_remotes=pending_name,
                timeout=timeout_time,
                timeout_remotes=pending_name,
            )
        )

        lm.start_request(remote_name)

        ################################################################
        # before: lock|remote_sync_vt|lock
        # remote_sync will get behind lock in request_setup
        # after : lock|remote_sync_rs|lock
        # should see smart_sync entry for remote_0
        ################################################################
        lm.advance_request()

        ################################################################
        # pend_sync will get behind lock in _verify_thread_is_current
        # locks held:
        # before: lock|remote_sync_rs|lock
        # after : lock|remote_sync_rs|lock|pend_sync_vt|lock
        ################################################################
        pend_sync_serial_num = self.add_cmd(
            Sync(
                cmd_runners=pending_name,
                targets=remote_name,
                sync_set_ack_remotes=remote_name,
            )
        )

        lm.start_request(pending_name)

        ################################################################
        # remote_sync will do setup and progress to start of request
        # loop
        # locks held:
        # before: lock|remote_sync_rs|lock|pend_sync_vt|lock
        # after : lock|pend_sync_vt|lock|remote_sync_rl|lock
        # should see remote_0 smart_sync setup complete
        ################################################################
        lm.advance_request()

        ################################################################
        # pend_sync will progress to setup
        # locks held:
        # before: lock|pend_sync_vt|lock|remote_sync_rl|lock
        # after : lock|remote_sync_rl|lock|pend_sync_rs|lock
        # should see smart_sync entry for pending_0
        ################################################################
        lm.advance_request()

        ################################################################
        # release lock to allow remote_sync to enter the request loop
        # and set the pending_name sync flag, and then get behind lock
        # before doing a second loop lap
        # locks held:
        # before: lock|remote_sync_rl|lock|pend_sync_rs|lock
        # after : lock|pend_sync_rs|lock|remote_sync_rl2|lock
        # should see remote_0 (test1) smart_sync set flag for pending_0
        ################################################################
        lm.advance_request()

        ################################################################
        # release lock to allow pend_sync to do setup and then wait
        # behind lock just before entering request loop
        # locks held:
        # before: lock|pend_sync_rs|lock|remote_sync_rl2|lock
        # after : lock|remote_sync_rl2|lock|pend_sync_rl|lock
        # should see pending_0 (test1) smart_sync setup complete
        ################################################################
        lm.advance_request()

        ################################################################
        # pause to cause remote_sync to timeout
        ################################################################
        self.add_cmd(Pause(cmd_runners=self.commander_name, pause_seconds=pause_time))

        ################################################################
        # release lock to allow remote_sync to enter the request loop
        # and see no progress from the pending_name, and then
        # timeout and get behind lock just before sync backout
        # locks held:
        # before: lock|remote_sync_rl2|lock|pend_sync_rl|lock
        # after : lock|pend_sync_rl|lock|remote_sync_sb
        ################################################################
        lm.advance_request(trailing_lock=False)

        ################################################################
        # release lock to allow pend_sync to enter the request loop
        # and set sync event for remote_sync and see that its sync event
        # is set and complete the sync request
        # locks held:
        # before: lock|pend_sync_rl|lock|remote_sync_sb
        # after : lock|remote_sync_sb
        # should see pending_0 (test1) smart_sync set flag for remote_0
        # and pending_0 (test1) smart_sync achieved with remote_0
        # and smart_sync exit: requestor: pending_0
        ################################################################
        lm.complete_request()

        ################################################################
        # Set the ack message for the completed sync by pend_sync.
        ################################################################
        pe = self.pending_events[pending_name]
        ack_key: AckKey = (remote_name, "smart_sync_achieved")

        pe[PE.ack_msg][ack_key] += 1

        ################################################################
        # release lock to allow remote_sync to enter the backout
        # routine to reset its sync event flag
        # locks held:
        # before: lock|remote_sync_sb
        # after : none
        # should see remote_0 (test1) smart_sync backout reset local
        # sync_flag for pending_0
        # and remote_0 (test1) raising SmartThreadRequestTimedOut
        ################################################################
        lm.complete_request()

        ################################################################
        # We also need to set the ack message for the backout.
        ################################################################
        pe = self.pending_events[remote_name]
        ack_key = (pending_name, "smart_sync_backout_local")

        pe[PE.ack_msg][ack_key] += 1

        ################################################################
        # verify the pending flags are as expected
        ################################################################
        exp_pending_flags = PendingFlags()
        self.add_cmd(
            VerifyConfig(
                cmd_runners=self.commander_name,
                verify_type=VerifyType.VerifyPendingFlags,
                names_to_check=pending_name,
                aux_names=remote_name,
                exp_pending_flags=exp_pending_flags,
                obtain_reg_lock=False,
            )
        )

        exp_pending_flags = PendingFlags()
        self.add_cmd(
            VerifyConfig(
                cmd_runners=self.commander_name,
                verify_type=VerifyType.VerifyPendingFlags,
                names_to_check=remote_name,
                aux_names=pending_name,
                exp_pending_flags=exp_pending_flags,
                obtain_reg_lock=False,
            )
        )

        ################################################################
        # confirm the remote_sync is done
        ################################################################
        self.add_cmd(
            ConfirmResponse(
                cmd_runners=self.commander_name,
                confirm_cmd="SyncTimeoutTrue",
                confirm_serial_num=remote_sync_serial_num,
                confirmers=remote_name,
            )
        )

        ################################################################
        # confirm the pend_sync is done
        ################################################################
        self.add_cmd(
            ConfirmResponse(
                cmd_runners=self.commander_name,
                confirm_cmd="Sync",
                confirm_serial_num=pend_sync_serial_num,
                confirmers=pending_name,
            )
        )

        ################################################################
        # verify config structures
        ################################################################
        self.add_cmd(
            VerifyConfig(
                cmd_runners=self.commander_name,
                verify_type=VerifyType.VerifyStructures,
                obtain_reg_lock=True,
            )
        )

    ####################################################################
    # build_send_unreg_receiver_scenario
    ####################################################################
    def build_send_unreg_receiver_scenario(self) -> None:
        """Return a list of ConfigCmd items for test scenario."""
        sender_names = get_names("sender_", 1)
        receiver_names = get_names("receiver_", 1)

        self.create_config(active_names=sender_names | receiver_names)

        ################################################################
        # setup the messages to send
        ################################################################
        sender_msgs = SendRecvMsgs(
            sender_names=sender_names,
            receiver_names=receiver_names,
            num_msgs=1,
            text="build_send_unreg_receiver_scenario",
        )

        ################################################################
        # receiver issues resume of sender to get sender del def
        ################################################################
        resume_serial_num = self.add_cmd(
            Resume(
                cmd_runners=receiver_names,
                targets=sender_names,
                exp_resumed_targets=sender_names,
            )
        )

        ################################################################
        # confirm the resume is done
        ################################################################
        self.add_cmd(
            ConfirmResponse(
                cmd_runners=self.commander_name,
                confirm_cmd="Resume",
                confirm_serial_num=resume_serial_num,
                confirmers=receiver_names,
            )
        )

        ################################################################
        # remove the receiver
        ################################################################
        self.build_exit_suite(
            cmd_runner=self.commander_name, names=receiver_names, validate_config=False
        )

        self.add_cmd(Join(cmd_runners=self.commander_name, join_names=receiver_names))

        ################################################################
        # issue the send to drive the path in _get_target_state that
        # sees receiver is not in the registry and it's pk_remote
        # create_time is zero, so it returns ThreadState.Unregistered
        ################################################################
        send_serial_num = self.add_cmd(
            SendMsgTimeoutTrue(
                cmd_runners=sender_names,
                receivers=receiver_names,
                exp_receivers=set(),
                timeout=1,
                unreg_timeout_names=receiver_names,
                fullq_timeout_names=set(),
                msgs_to_send=sender_msgs,
                msg_idx=0,
            )
        )

        ################################################################
        # confirm the send is done
        ################################################################
        self.add_cmd(
            ConfirmResponse(
                cmd_runners=self.commander_name,
                confirm_cmd="SendMsgTimeoutTrue",
                confirm_serial_num=send_serial_num,
                confirmers=sender_names,
            )
        )

        ################################################################
        # verify config structures
        ################################################################
        self.add_cmd(
            VerifyConfig(
                cmd_runners=self.commander_name,
                verify_type=VerifyType.VerifyStructures,
                obtain_reg_lock=True,
            )
        )

    ####################################################################
    # build_join_simple_timeout_scenario
    ####################################################################
    def build_join_simple_timeout_scenario(self) -> None:
        """Return a list of ConfigCmd items for test scenario."""
        target_names = get_names("target_", 1)
        joiner_names = get_names("joiner_", 1)

        self.create_config(reg_names=target_names, active_names=joiner_names)

        timeout_time = 0.5
        ################################################################
        # join
        ################################################################
        join_serial_num = self.add_cmd(
            JoinTimeoutTrue(
                cmd_runners=joiner_names,
                join_names=target_names,
                timeout=timeout_time,
                timeout_names=target_names,
            )
        )

        ################################################################
        # confirm the join is done
        ################################################################
        self.add_cmd(
            ConfirmResponse(
                cmd_runners=self.commander_name,
                confirm_cmd="JoinTimeoutTrue",
                confirm_serial_num=join_serial_num,
                confirmers=joiner_names,
            )
        )

        ################################################################
        # verify config structures
        ################################################################
        self.add_cmd(
            VerifyConfig(
                cmd_runners=self.commander_name,
                verify_type=VerifyType.VerifyStructures,
                obtain_reg_lock=True,
            )
        )

    ####################################################################
    # build_wait_simple_deadlock_scenario
    ####################################################################
    def build_wait_simple_deadlock_scenario(self) -> None:
        """Return a list of ConfigCmd items for test scenario."""
        waiter_names = get_names("waiter_", 2)

        self.create_config(active_names=waiter_names)

        ################################################################
        # waiter_0
        ################################################################
        wait_0_serial_num = self.add_cmd(
            Wait(
                cmd_runners="waiter_0",
                resumers="waiter_1",
                exp_resumers=set(),
                deadlock_remotes="waiter_1",
            )
        )

        ################################################################
        # waiter_1
        ################################################################
        wait_1_serial_num = self.add_cmd(
            Wait(
                cmd_runners="waiter_1",
                resumers="waiter_0",
                exp_resumers=set(),
                deadlock_remotes="waiter_0",
            )
        )

        ################################################################
        # confirm the wait_0 is done
        ################################################################
        self.add_cmd(
            ConfirmResponse(
                cmd_runners=self.commander_name,
                confirm_cmd="Wait",
                confirm_serial_num=wait_0_serial_num,
                confirmers="waiter_0",
            )
        )

        ################################################################
        # confirm the wait_1 is done
        ################################################################
        self.add_cmd(
            ConfirmResponse(
                cmd_runners=self.commander_name,
                confirm_cmd="Wait",
                confirm_serial_num=wait_1_serial_num,
                confirmers="waiter_1",
            )
        )

        ################################################################
        # verify config structures
        ################################################################
        self.add_cmd(
            VerifyConfig(
                cmd_runners=self.commander_name,
                verify_type=VerifyType.VerifyStructures,
                obtain_reg_lock=True,
            )
        )

    ####################################################################
    # build_sync_unreg_simple_scenario
    ####################################################################
    def build_sync_unreg_simple_scenario(self) -> None:
        """Return a list of ConfigCmd items for test scenario."""
        self.create_config(reg_names={"sync_0"}, active_names={"sync_1"})

        timeout_time = 0.5
        ################################################################
        # waiter_0
        ################################################################
        sync_1_serial_num = self.add_cmd(
            SyncTimeoutTrue(
                cmd_runners="sync_1",
                targets="sync_0",
                timeout=timeout_time,
                timeout_remotes="sync_0",
                sync_set_ack_remotes=set(),
            )
        )

        ################################################################
        # confirm the wait_1 is done
        ################################################################
        self.add_cmd(
            ConfirmResponse(
                cmd_runners=self.commander_name,
                confirm_cmd="SyncTimeoutTrue",
                confirm_serial_num=sync_1_serial_num,
                confirmers="sync_1",
            )
        )

        ################################################################
        # verify config structures
        ################################################################
        self.add_cmd(
            VerifyConfig(
                cmd_runners=self.commander_name,
                verify_type=VerifyType.VerifyStructures,
                obtain_reg_lock=True,
            )
        )

    ####################################################################
    # build_sync_init_delay_scenario
    ####################################################################
    def build_sync_init_delay_scenario(self) -> None:
        """Return a list of ConfigCmd items for test scenario.

        This test will drive the check of the create time for zero:

            1) create sync_0
            2) get lock
            3) sync_0 does smart_sync with sync_1
            4) get lock
            5) create sync_1 (swap sync_0 and sync_1 to keep sync_0
               from advancing, so it maintains a zero create time for
               sync_1 in its pk_remote)
            6) sync_1 does smart_sync - sees sync_0 has zero create
               time for sync_1, and therefore succeeds in doing the sync

        """
        # self.auto_calling_refresh_msg = False
        sync_names = ["sync_0", "sync_1"]

        locker_names = ["locker_0", "locker_1", "locker_2", "locker_3", "locker_4"]
        lm = LockMgr(config_ver=self, locker_names=locker_names)

        aux_names = ["aux_0"]

        self.create_config(
            unreg_names=[sync_names[1]],
            active_names=([sync_names[0]] + locker_names + aux_names),
        )

        ################################################################
        # The following are appended to the requestor names:
        #     _v means request is behind lock in
        #        _verify_thread_is_current
        #     _s means request is behind lock just before request setup
        #     _r means request is behind lock just before request loop
        #     _e means request is behind lock in error path
        #     -reg means register for smart_init
        ################################################################

        ################################################################
        # before: none
        # action: get lock
        # after : lock
        ################################################################
        lm.get_lock()

        ################################################################
        # before: lock
        # action: sync_0a
        # after : lock|sync_0a_v|lock
        ################################################################
        sync_0a_serial_num = self.add_cmd(
            Sync(
                cmd_runners=sync_names[0],
                targets=sync_names[1],
                sync_set_ack_remotes=sync_names[1],
            )
        )
        lm.start_request(sync_names[0])

        ################################################################
        # before: lock|sync_0a_v|lock
        # action: drop lock, sync_0 does verify and wait at setup
        # after : lock_0|sync_0a_s|lock
        ################################################################
        lm.advance_request()

        ################################################################
        # before: lock|sync_0a_s|lock
        # action: drop lock, sync_0 does setup, waits at req loop
        # after : lock_0|sync_0a_r|lock
        ################################################################
        lm.advance_request()

        ################################################################
        # before: lock|sync_0a_r|lock
        # action: create and start sync_1
        # after : lock|sync_0a_r|lock|aux_0_reg|lock
        ################################################################
        self.unregistered_names -= {sync_names[1]}
        self.add_cmd(
            CreateF1AutoStart(
                cmd_runners=aux_names[0],
                f1_create_items=[
                    F1CreateItem(
                        name=sync_names[1],
                        auto_start=True,
                        target_rtn=outer_f1,
                        app_config=AppConfig.ScriptStyle,
                    )
                ],
            )
        )

        self.active_names |= {sync_names[1]}

        lm.start_request(aux_names[0])

        ################################################################
        # before: lock|sync_0a_r|lock|aux_0_reg|lock
        # action: swap sync_0 and aux_0_reg
        # after : lock|aux_0_reg|lock|sync_0a_r|lock
        ################################################################
        lm.swap_requestors()

        ################################################################
        # before: lock|aux_0_reg|lock|sync_0a_r|lock
        # action: drop lock, aux_0 does register, then goes to
        #             smart_start setup
        # after : lock|sync_0a_r|lock|aux_0_s|lock
        ################################################################
        lm.advance_request()

        ################################################################
        # before: lock|sync_0a_r|lock|aux_0_s|lock
        # action: swap sync_0 and aux_0_s
        # after : lock|aux_0_s|lock|sync_0a_r|lock
        ################################################################
        lm.swap_requestors()

        ################################################################
        # before: lock|aux_0_s|lock|sync_0a_r|lock
        # action: drop lock, aux_0 completes smart_start
        # after : lock|sync_0a_r|lock
        ################################################################
        lm.complete_request()

        ################################################################
        # before: lock|sync_0a_r|lock
        # action: sync_1a_s
        # after : lock|sync_0a_r|lock|sync_1a_v|lock
        ################################################################
        sync_1a_serial_num = self.add_cmd(
            Sync(
                cmd_runners=sync_names[1],
                targets=sync_names[0],
                sync_set_ack_remotes=sync_names[0],
            )
        )
        lm.start_request(sync_names[1])

        ################################################################
        # before: lock|sync_0a_r|lock|sync_1a_v|lock
        # action: swap sync_0 and sync_1a_v
        # after : lock|sync_1a_v|lock|sync_0a_r|lock
        ################################################################
        lm.swap_requestors()

        ################################################################
        # before: lock|sync_1a_v|lock|sync_0a_r|lock
        # action: swap sync_0 and sync_1a_v
        # after : lock|sync_0a_r|lock||sync_1a_s|lock
        ################################################################
        lm.advance_request()

        ################################################################
        # before: lock|sync_0a_r|lock|sync_1a_s|lock
        # action: swap sync_0 and sync_1a_s
        # after : lock|sync_1a_s|lock|sync_0a_r|lock
        ################################################################
        lm.swap_requestors()

        ################################################################
        # before: lock|sync_1a_s|lock|sync_0a_r|lock
        # action: drop lock, sync_1a_s completes setup and gets
        #             behind lock in req loop
        # after : lock|sync_0a_r|lock|sync_1a_r|lock
        ################################################################
        lm.advance_request()

        ################################################################
        # before: lock|sync_0a_r|lock|sync_1a_r|lock
        # action: swap sync_0a and sync_1a_s
        # after : lock|sync_1a_r|lock|sync_0a_r|lock
        ################################################################
        lm.swap_requestors()

        ################################################################
        # verify sync_0 has zero create time for sync_1
        ################################################################
        check_pend_arg: CheckZeroCtArg = (sync_names[0], sync_names[1])
        self.add_cmd(
            WaitForCondition(
                cmd_runners=self.commander_name,
                check_rtn=self.check_sync_zero_create_time,
                check_args=check_pend_arg,
            )
        )

        ################################################################
        # before: lock|sync_1a_r|lock|sync_0a_r|lock
        # action: drop lock, sync_1a_r sees sync_0 has zero create
        #             time for sync_1, so sync_1 sets sync_0 sync_flag
        #             and loops back to top of req loop to let sync_0
        #             sync up
        # after : lock|sync_0a_r|lock|sync_1a_r
        ################################################################
        lm.advance_request(trailing_lock=False)

        ################################################################
        # before: lock|sync_0a_r|lock|sync_1a_r
        # action: drop lock, sync_0 sees that sync_1 is alive and
        #             sets sync_1 sync_flag, sees its sync_flag is
        #             set and completes the sync request
        # after : lock|sync_1a_r
        ################################################################
        lm.complete_request()

        ################################################################
        # before: lock|sync_1a_r
        # action: drop lock, sync_1 sees sync_0 has set sync_1
        #             sync and completes
        # after : none
        ################################################################
        lm.complete_request()

        ################################################################
        # confirm the sync requests
        ################################################################
        self.add_cmd(
            ConfirmResponse(
                cmd_runners=self.commander_name,
                confirm_cmd="Sync",
                confirm_serial_num=sync_0a_serial_num,
                confirmers=sync_names[0],
            )
        )

        self.add_cmd(
            ConfirmResponse(
                cmd_runners=self.commander_name,
                confirm_cmd="Sync",
                confirm_serial_num=sync_1a_serial_num,
                confirmers=sync_names[1],
            )
        )

        ################################################################
        # verify config structures
        ################################################################
        self.add_cmd(
            VerifyConfig(
                cmd_runners=self.commander_name,
                verify_type=VerifyType.VerifyStructures,
                obtain_reg_lock=True,
            )
        )

    ####################################################################
    # build_sync_partial_scenario
    ####################################################################
    def build_sync_partial_scenario(
        self,
        sync_0_targets: int,
        sync_1_targets: int,
        sync_2_targets: int,
        sync_3_targets: int,
    ) -> None:
        """Return a list of ConfigCmd items for test scenario."""
        sync_names = ["sync_0", "sync_1", "sync_2", "sync_3"]

        self.create_config(active_names=sync_names)

        targets: dict[int, set[str]] = {
            1: {"sync_0"},
            2: {"sync_1"},
            3: {"sync_1", "sync_0"},
            4: {"sync_2"},
            5: {"sync_2", "sync_0"},
            6: {"sync_2", "sync_1"},
            7: {"sync_2", "sync_1", "sync_0"},
            8: {"sync_3"},
            9: {"sync_3", "sync_0"},
            10: {"sync_3", "sync_1"},
            11: {"sync_3", "sync_1", "sync_0"},
            12: {"sync_3", "sync_2"},
            13: {"sync_3", "sync_2", "sync_0"},
            14: {"sync_3", "sync_2", "sync_1"},
            15: {"sync_3", "sync_2", "sync_1", "sync_0"},
        }

        sync_0_target_set = targets[sync_0_targets].copy()
        sync_1_target_set = targets[sync_1_targets].copy()
        sync_2_target_set = targets[sync_2_targets].copy()
        sync_3_target_set = targets[sync_3_targets].copy()

        if "sync_0" in sync_1_target_set:
            sync_0_target_set |= {"sync_1"}
        if "sync_0" in sync_2_target_set:
            sync_0_target_set |= {"sync_2"}
        if "sync_0" in sync_3_target_set:
            sync_0_target_set |= {"sync_3"}

        if "sync_1" in sync_0_target_set:
            sync_1_target_set |= {"sync_0"}
        if "sync_1" in sync_2_target_set:
            sync_1_target_set |= {"sync_2"}
        if "sync_1" in sync_3_target_set:
            sync_1_target_set |= {"sync_3"}

        if "sync_2" in sync_0_target_set:
            sync_2_target_set |= {"sync_0"}
        if "sync_2" in sync_1_target_set:
            sync_2_target_set |= {"sync_1"}
        if "sync_2" in sync_3_target_set:
            sync_2_target_set |= {"sync_3"}

        if "sync_3" in sync_0_target_set:
            sync_3_target_set |= {"sync_0"}
        if "sync_3" in sync_1_target_set:
            sync_3_target_set |= {"sync_1"}
        if "sync_3" in sync_2_target_set:
            sync_3_target_set |= {"sync_2"}

        ################################################################
        # sync_0
        ################################################################
        sync_0_serial_num = self.add_cmd(
            Sync(
                cmd_runners="sync_0",
                targets=sync_0_target_set,
                sync_set_ack_remotes=sync_0_target_set,
            )
        )

        ################################################################
        # sync_1
        ################################################################
        sync_1_serial_num = self.add_cmd(
            Sync(
                cmd_runners="sync_1",
                targets=sync_1_target_set,
                sync_set_ack_remotes=sync_1_target_set,
            )
        )

        ################################################################
        # sync_2
        ################################################################
        sync_2_serial_num = self.add_cmd(
            Sync(
                cmd_runners="sync_2",
                targets=sync_2_target_set,
                sync_set_ack_remotes=sync_2_target_set,
            )
        )

        ################################################################
        # sync_3
        ################################################################
        sync_3_serial_num = self.add_cmd(
            Sync(
                cmd_runners="sync_3",
                targets=sync_3_target_set,
                sync_set_ack_remotes=sync_3_target_set,
            )
        )

        ################################################################
        # confirm sync_0
        ################################################################
        self.add_cmd(
            ConfirmResponse(
                cmd_runners=self.commander_name,
                confirm_cmd="Sync",
                confirm_serial_num=sync_0_serial_num,
                confirmers="sync_0",
            )
        )

        ################################################################
        # confirm sync_1
        ################################################################
        self.add_cmd(
            ConfirmResponse(
                cmd_runners=self.commander_name,
                confirm_cmd="Sync",
                confirm_serial_num=sync_1_serial_num,
                confirmers="sync_1",
            )
        )

        ################################################################
        # confirm sync_2
        ################################################################
        self.add_cmd(
            ConfirmResponse(
                cmd_runners=self.commander_name,
                confirm_cmd="Sync",
                confirm_serial_num=sync_2_serial_num,
                confirmers="sync_2",
            )
        )

        ################################################################
        # confirm sync_3
        ################################################################
        self.add_cmd(
            ConfirmResponse(
                cmd_runners=self.commander_name,
                confirm_cmd="Sync",
                confirm_serial_num=sync_3_serial_num,
                confirmers="sync_3",
            )
        )

        ################################################################
        # verify config structures
        ################################################################
        self.add_cmd(
            VerifyConfig(
                cmd_runners=self.commander_name,
                verify_type=VerifyType.VerifyStructures,
                obtain_reg_lock=True,
            )
        )

    ####################################################################
    # check_pending_events
    ####################################################################
    def check_expected_responses(
        self, cmd_runner: str, check_args: CheckExpectedResponsesArgs
    ) -> bool:
        """Check that the sync event is set in the target_rtn.

        Args:
            cmd_runner: thread name doing the check
            check_args: requestors, targets, and request type
        """
        for requestor in check_args.requestors:
            if requestor not in self.expected_registered:
                raise InvalidConfigurationDetected(
                    f"check_expected_responses {cmd_runner=} detected "
                    f"that {requestor=} is not in expected_registered."
                )
            if check_args.request == st.ReqType.Smart_recv:
                if check_args.exp_response_targets != set(
                    self.expected_registered[requestor].thread.recvd_msgs.keys()
                ):
                    return False
            else:
                raise InvalidInputDetected(
                    f"check_expected_responses {cmd_runner=} detected "
                    f"unknown {check_args.request=}."
                )

        return True

    ####################################################################
    # check_sync_event_set
    ####################################################################
    def check_sync_event_set(self, cmd_runner: str, check_args: CheckPendArg) -> bool:
        """Check that the sync event is set in the target_rtn.

        Args:
            cmd_runner: thread name doing the check
            check_args: target_rtn name and pair_key to be checked
        """
        target = check_args[0]
        pair_key = check_args[1]
        if target not in self.expected_registered:
            raise InvalidConfigurationDetected(
                f"check_sync_event_set {target=} not in expected_registered"
            )

        if pair_key not in self.expected_pairs:
            raise InvalidConfigurationDetected(
                f"check_sync_event_set {pair_key=} not in expected_pairs"
            )

        if target not in self.expected_pairs[pair_key]:
            raise InvalidConfigurationDetected(
                f"check_sync_event_set {target=} not in expected_pairs"
                f"with {pair_key=}"
            )

        if self.expected_pairs[pair_key][target].pending_sync:
            return True

        return False

    ####################################################################
    # check_sync_zero_create_time
    ####################################################################
    def check_sync_zero_create_time(
        self, cmd_runner: str, check_args: CheckZeroCtArg
    ) -> bool:
        """Check that the sync event is set in the target_rtn.

        Args:
            cmd_runner: thread name doing the check
            check_args: target_rtn name and pair_key to be checked
        """
        sync_0 = check_args[0]
        sync_1 = check_args[1]

        pair_key = st.SmartThread._get_pair_key(sync_0, sync_1)
        pk_remote: st.PairKeyRemote = st.PairKeyRemote(
            pair_key=pair_key, remote=sync_1, create_time=0.0
        )
        if sync_0 not in self.expected_registered:
            raise InvalidConfigurationDetected(
                f"check_sync_zero_create_time {sync_0=} not in " "expected_registered"
            )
        if sync_1 not in self.expected_registered:
            raise InvalidConfigurationDetected(
                f"check_sync_zero_create_time {sync_1=} not in " "expected_registered"
            )

        if pk_remote in self.expected_registered[sync_0].thread.work_pk_remotes:
            return True

        return False

    ####################################################################
    # check_pending_events
    ####################################################################
    def check_pending_events(self, verify_idx: int) -> None:
        """Check pending events are clear.

        Args:
            verify_idx: contains verify index to snapshot data
        """
        incomplete_items: dict[str, dict[PE, Any]] = {}
        for cmd_runner, pend_events in self.pending_events.items():
            for event_name, item in pend_events.items():
                if isinstance(item, defaultdict):
                    for key, item2 in item.items():
                        if item2 != 0:
                            if cmd_runner not in incomplete_items:
                                incomplete_items[cmd_runner] = {}
                            if event_name not in incomplete_items[cmd_runner]:
                                incomplete_items[cmd_runner][event_name] = {}
                            incomplete_items[cmd_runner][event_name][key] = item2
                elif isinstance(item, int):
                    if item != 0:
                        if cmd_runner not in incomplete_items:
                            incomplete_items[cmd_runner] = {}
                        incomplete_items[cmd_runner][event_name] = item
                elif isinstance(item, deque):
                    if len(item) != 0:
                        if cmd_runner not in incomplete_items:
                            incomplete_items[cmd_runner] = {}
                        incomplete_items[cmd_runner][event_name] = item
                elif isinstance(item, StartRequest):
                    if item.req_type != st.ReqType.NoReq:
                        if cmd_runner not in incomplete_items:
                            incomplete_items[cmd_runner] = {}
                        incomplete_items[cmd_runner][event_name] = item
                else:
                    raise UnrecognizedEvent(
                        "check_pending_events does not recognize"
                        f"event {event_name=}, {item=}"
                    )

        if incomplete_items:
            for cmd_runner, item in incomplete_items.items():
                self.log_test_msg(f"incomplete_item: {cmd_runner=}, {item=}")
            raise RemainingPendingEvents(
                "check_pending_events detected that there are remaining "
                f"pending items:\n {incomplete_items=}"
            )

    ####################################################################
    # build_def_del_scenario
    ####################################################################
    def build_def_del_scenario(self, def_del_scenario: DefDelScenario) -> None:
        """Return a list of ConfigCmd items for a deferred delete.

        Args:
            def_del_scenario: specifies type of test to do

        """
        self.auto_calling_refresh_msg = False
        num_receivers = 2
        num_senders = 1

        num_waiters = 2
        num_resumers = 1

        num_syncers = 2

        num_dels = 1
        num_adds = 1

        num_deleters = 1
        num_adders = 1

        num_lockers = 5

        num_active_needed = (
            num_receivers
            + num_senders
            + num_waiters
            + num_resumers
            + num_syncers
            + num_dels
            + num_deleters
            + num_adders
            + num_lockers
            + 1
        )  # plus 1 for the commander
        self.build_config(cmd_runner=self.commander_name, num_active=num_active_needed)

        active_names_copy = self.active_names - {self.commander_name}

        ################################################################
        # choose receiver_names
        ################################################################
        receiver_names = self.choose_names(
            name_collection=active_names_copy,
            num_names_needed=num_receivers,
            update_collection=True,
            var_name_for_log="receiver_names",
        )

        ################################################################
        # choose sender_names
        ################################################################
        sender_names = self.choose_names(
            name_collection=active_names_copy,
            num_names_needed=num_senders,
            update_collection=True,
            var_name_for_log="sender_names",
        )

        ################################################################
        # choose waiter_names
        ################################################################
        waiter_names = self.choose_names(
            name_collection=active_names_copy,
            num_names_needed=num_waiters,
            update_collection=True,
            var_name_for_log="waiter_names",
        )

        ################################################################
        # choose resumer_names
        ################################################################
        resumer_names = self.choose_names(
            name_collection=active_names_copy,
            num_names_needed=num_resumers,
            update_collection=True,
            var_name_for_log="resumer_names",
        )

        ################################################################
        # choose del_names
        ################################################################
        del_names = self.choose_names(
            name_collection=active_names_copy,
            num_names_needed=num_dels,
            update_collection=True,
            var_name_for_log="del_names",
        )

        ################################################################
        # choose add_names
        ################################################################
        unregistered_names_copy = self.unregistered_names.copy()
        add_names = self.choose_names(
            name_collection=unregistered_names_copy,
            num_names_needed=num_adds,
            update_collection=True,
            var_name_for_log="add_names",
        )

        ################################################################
        # choose deleter_names
        ################################################################
        deleter_names = self.choose_names(
            name_collection=active_names_copy,
            num_names_needed=num_deleters,
            update_collection=True,
            var_name_for_log="deleter_names",
        )

        ################################################################
        # choose adder_names
        ################################################################
        adder_names = self.choose_names(
            name_collection=active_names_copy,
            num_names_needed=num_adders,
            update_collection=True,
            var_name_for_log="adder_names",
        )

        ################################################################
        # choose locker_names
        ################################################################
        locker_names = self.choose_names(
            name_collection=active_names_copy,
            num_names_needed=num_lockers,
            update_collection=True,
            var_name_for_log="locker_names",
        )
        lm = LockMgr(config_ver=self, locker_names=locker_names)

        ################################################################
        # Categorize the request types
        ################################################################
        single_request = False
        double_request = False
        del_add_request = False

        cmd_0_name: str = ""
        cmd_0_smart_name = ""
        cmd_0_confirmer: str = ""
        recv_0_name: str = ""
        wait_0_name: str = ""

        cmd_1_name: str = ""
        cmd_1_smart_name = ""
        cmd_1_confirmer: str = ""
        cmd_1_serial_num: int = 0
        recv_1_name: str = ""
        wait_1_name: str = ""

        receivers: list[str] = []
        waiters: list[str] = []

        if (
            def_del_scenario == DefDelScenario.NormalRecv
            or def_del_scenario == DefDelScenario.ResurrectionRecv
            or def_del_scenario == DefDelScenario.NormalWait
            or def_del_scenario == DefDelScenario.ResurrectionWait
        ):
            single_request = True

        elif (
            def_del_scenario == DefDelScenario.Recv0Recv1
            or def_del_scenario == DefDelScenario.Recv1Recv0
            or def_del_scenario == DefDelScenario.WaitRecv
            or def_del_scenario == DefDelScenario.Wait0Wait1
            or def_del_scenario == DefDelScenario.Wait1Wait0
            or def_del_scenario == DefDelScenario.RecvWait
        ):
            double_request = True

        elif (
            def_del_scenario == DefDelScenario.RecvDel
            or def_del_scenario == DefDelScenario.WaitDel
            or def_del_scenario == DefDelScenario.RecvAdd
            or def_del_scenario == DefDelScenario.WaitAdd
        ):
            del_add_request = True

        ################################################################
        # Determine whether first request is smart_recv or wait
        ################################################################
        if (
            def_del_scenario == DefDelScenario.NormalRecv
            or def_del_scenario == DefDelScenario.ResurrectionRecv
            or def_del_scenario == DefDelScenario.Recv0Recv1
            or def_del_scenario == DefDelScenario.Recv1Recv0
            or def_del_scenario == DefDelScenario.RecvWait
            # or def_del_scenario == DefDelScenario.WaitRecv
            or def_del_scenario == DefDelScenario.RecvDel
            or def_del_scenario == DefDelScenario.RecvAdd
        ):
            cmd_0_name = "RecvMsg"
            cmd_0_smart_name = "smart_recv"
            recv_0_name = receiver_names[0]
            cmd_0_confirmer = recv_0_name
            receivers.append(recv_0_name)

        elif (
            def_del_scenario == DefDelScenario.NormalWait
            or def_del_scenario == DefDelScenario.ResurrectionWait
            or def_del_scenario == DefDelScenario.Wait0Wait1
            or def_del_scenario == DefDelScenario.Wait1Wait0
            # or def_del_scenario == DefDelScenario.RecvWait
            or def_del_scenario == DefDelScenario.WaitRecv
            or def_del_scenario == DefDelScenario.WaitDel
            or def_del_scenario == DefDelScenario.WaitAdd
        ):
            cmd_0_name = "Wait"
            cmd_0_smart_name = "smart_wait"
            wait_0_name = waiter_names[0]
            cmd_0_confirmer = wait_0_name
            waiters.append(wait_0_name)

        ################################################################
        # Determine whether second request (if one) is smart_recv or
        # wait
        ################################################################
        if (
            def_del_scenario == DefDelScenario.Recv0Recv1
            or def_del_scenario == DefDelScenario.Recv1Recv0
            or def_del_scenario == DefDelScenario.WaitRecv
        ):
            if def_del_scenario == DefDelScenario.WaitRecv:
                recv_1_name = receiver_names[0]
            else:
                recv_1_name = receiver_names[1]
            cmd_1_name = "RecvMsg"
            cmd_1_smart_name = "smart_recv"
            receivers.append(recv_1_name)

        elif (
            def_del_scenario == DefDelScenario.Wait0Wait1
            or def_del_scenario == DefDelScenario.Wait1Wait0
            or def_del_scenario == DefDelScenario.RecvWait
        ):
            if def_del_scenario == DefDelScenario.RecvWait:
                wait_1_name = waiter_names[0]
            else:
                wait_1_name = waiter_names[1]
            cmd_1_name = "Wait"
            cmd_1_smart_name = "smart_wait"
            waiters.append(wait_1_name)

        exiters: list[str] = []
        if (
            def_del_scenario == DefDelScenario.RecvDel
            or def_del_scenario == DefDelScenario.WaitDel
        ):
            exiters.append(del_names[0])

        adders: list[str] = []
        if (
            def_del_scenario == DefDelScenario.RecvAdd
            or def_del_scenario == DefDelScenario.WaitAdd
        ):
            adders.append(add_names[0])

        exit_names: list[str] = []
        if receivers:
            ############################################################
            # send a msg that will sit on the smart_recv msg_q (1 or 2)
            ############################################################
            exit_names.append(sender_names[0])

            sender_msgs = SendRecvMsgs(
                sender_names=sender_names,
                receiver_names=receivers,
                num_msgs=1,
                text="build_def_del_scenario",
            )
            send_msg_serial_num_0 = self.add_cmd(
                SendMsg(
                    cmd_runners=sender_names[0],
                    receivers=receivers,
                    exp_receivers=receivers,
                    msgs_to_send=sender_msgs,
                    msg_idx=0,
                )
            )
            self.add_cmd(
                ConfirmResponse(
                    cmd_runners=[self.commander_name],
                    confirm_cmd="SendMsg",
                    confirm_serial_num=send_msg_serial_num_0,
                    confirmers=sender_names[0],
                )
            )
        if waiters:
            ############################################################
            # resume that will set wait bit
            ############################################################
            exit_names.append(resumer_names[0])
            resume_serial_num_0 = self.add_cmd(
                Resume(
                    cmd_runners=resumer_names[0],
                    targets=waiters,
                    exp_resumed_targets=waiters,
                    stopped_remotes=[],
                )
            )
            self.add_cmd(
                ConfirmResponse(
                    cmd_runners=[self.commander_name],
                    confirm_cmd="Resume",
                    confirm_serial_num=resume_serial_num_0,
                    confirmers=resumer_names[0],
                )
            )

        if (
            def_del_scenario != DefDelScenario.NormalRecv
            and def_del_scenario != DefDelScenario.NormalWait
        ):
            ############################################################
            # exit the sender to create a half paired case
            ############################################################
            self.build_exit_suite(
                cmd_runner=self.commander_name, names=exit_names, validate_config=False
            )
            self.build_join_suite(
                cmd_runners=self.commander_name,
                join_target_names=exit_names,
                validate_config=False,
            )

            if (
                def_del_scenario == DefDelScenario.ResurrectionRecv
                or def_del_scenario == DefDelScenario.ResurrectionWait
            ):
                ########################################################
                # resurrect the sender
                ########################################################
                f1_create_items: list[F1CreateItem] = []
                for idx, name in enumerate(exit_names):
                    if idx % 2:
                        app_config = AppConfig.ScriptStyle
                    else:
                        app_config = AppConfig.RemoteThreadApp

                    f1_create_items.append(
                        F1CreateItem(
                            name=name,
                            auto_start=True,
                            target_rtn=outer_f1,
                            app_config=app_config,
                        )
                    )
                self.build_create_suite(
                    f1_create_items=f1_create_items, validate_config=False
                )

        ################################################################
        # For scenarios that have a second request, get lock 0 to keep
        # the first smart_recv/wait progressing beyond the lock obtain
        # in _request_setup where the pk_remotes list is built.
        ################################################################
        if not single_request:
            ############################################################
            # before: none
            # action: get lock
            # after: lock
            ############################################################
            lm.get_lock()

        ################################################################
        # do the first recv or wait
        ################################################################
        if cmd_0_name == "RecvMsg":
            cmd_0_serial_num = self.add_cmd(
                RecvMsg(
                    cmd_runners=recv_0_name,
                    senders=sender_names[0],
                    exp_msgs=sender_msgs,
                    exp_senders=sender_names[0],
                    log_msg="def_del_recv_test_0",
                )
            )
            if not single_request:
                ########################################################
                # before: lock
                # action: RecvMsg
                # after: lock|recv_0_v|lock
                ########################################################
                lm.start_request(recv_0_name)

        else:  # must be wait
            cmd_0_serial_num = self.add_cmd(
                Wait(
                    cmd_runners=wait_0_name,
                    resumers=resumer_names[0],
                    exp_resumers=resumer_names[0],
                    stopped_remotes=set(),
                    log_msg="def_del_wait_test_0",
                )
            )
            if not single_request:
                ########################################################
                # before: lock
                # action: Wait
                # after: lock|wait_0_v|lock
                ########################################################
                lm.start_request(wait_0_name)

        ################################################################
        # Note: in the lock verify comments, the 'a', 'b', 'c', or 'd'
        # chars appended to request_0 and request_1 indicate where the
        # request is positioned along the path:
        # 'v' means behind the lock in _verify_thread_is_current
        # 's' means behind the lock in _request_setup
        # 'r' means behind the lock in _request_loop
        # 'f' means behind the lock before doing a refresh pair_array
        # 'i' means the lock in register for add
        ################################################################

        ################################################################
        # From this point on we will split the scenarios into separate
        # build paths to simplify the lock manipulations
        ################################################################
        if double_request:
            if cmd_1_name == "RecvMsg":
                cmd_1_confirmer = recv_1_name
                cmd_1_serial_num = self.add_cmd(
                    RecvMsg(
                        cmd_runners=recv_1_name,
                        senders=sender_names[0],
                        exp_senders=sender_names[0],
                        exp_msgs=sender_msgs,
                        log_msg="def_del_recv_test_1",
                    )
                )
                ########################################################
                # before: lock|recv_0_v|lock
                # or:     lock|wait_0_v|lock
                # action: Wait
                # after: lock|recv_0_v|lock|recv_1_v|lock
                # or:    lock|wait_0_v|lock|recv_1_v|lock
                ########################################################
                lm.start_request(recv_1_name)

            else:  # must be wait
                cmd_1_confirmer = wait_1_name
                cmd_1_serial_num = self.add_cmd(
                    Wait(
                        cmd_runners=wait_1_name,
                        resumers=resumer_names[0],
                        exp_resumers=resumer_names[0],
                        stopped_remotes=set(),
                        log_msg="def_del_wait_test_1",
                    )
                )
                ########################################################
                # before: lock|recv_0_v|lock
                # or:     lock|wait_0_v|lock
                # action: Wait
                # after: lock|recv_0_v|lock|wait_1_1_v|lock
                # or:    lock|wait_0_v|lock|wait_1_1_v|lock
                ########################################################
                lm.start_request(wait_1_name)

            ############################################################
            # before: lock|req_0_v|lock|req_1_v|lock
            # action: drop lock to allow first req to advance to setup
            # after: lock|req_1_v|lock|req_0_s|lock
            ############################################################
            lm.advance_request()

            ############################################################
            # before: lock|req_1_v|lock|req_0_s|lock
            # action: drop lock to allow first req to advance to setup
            # after: lock|req_0_s|lock|req_1_s|lock
            ############################################################
            lm.advance_request()

            ############################################################
            # complete the build in part a
            ############################################################
            self.build_def_del_scenario_part_a(
                def_del_scenario=def_del_scenario,
                lm=lm,
            )
        elif del_add_request:
            ############################################################
            # for del and add, we need to progress request_0 from v to r
            ############################################################
            ############################################################
            # release lock_0
            ############################################################
            ############################################################
            # before: lock|req_0_v|lock
            # action: drop lock to allow first req to advance to setup
            # after:  lock|req_0_s|lock
            ############################################################
            lm.advance_request()

            ############################################################
            # do the del or add request
            ############################################################
            if (
                def_del_scenario == DefDelScenario.RecvDel
                or def_del_scenario == DefDelScenario.WaitDel
            ):
                self.build_exit_suite(
                    cmd_runner=deleter_names[0],
                    names=[del_names[0]],
                    validate_config=False,
                )
                self.build_join_suite(
                    cmd_runners=deleter_names[0],
                    join_target_names=[del_names[0]],
                    validate_config=False,
                )
                ########################################################
                # before: lock|req_0_s|lock
                # action: smart_join
                # after:  lock|req_0_s|lock|smart_join_v|lock
                ########################################################
                lm.start_request(deleter_names[0])

                ########################################################
                # before: lock|req_0_s|lock|smart_join_v|lock
                # action: drop lock
                # after:  lock|smart_join_v|lock|req_0_r
                ########################################################
                lm.advance_request(trailing_lock=False)

                ########################################################
                # before: lock|smart_join_v|lock|req_0_r
                # action: drop lock
                # after:  lock|req_0_r|smart_join_r
                ########################################################
                lm.advance_request(trailing_lock=False)
            else:  # must be add
                ########################################################
                # before: lock|req_0_s|lock
                # action: drop lock to allow first req to advance to
                #         request loop
                # after:  lock|req_0_r
                ########################################################
                lm.advance_request(trailing_lock=False)

                ########################################################
                # smart_init
                ########################################################
                f1_create_items = [
                    F1CreateItem(
                        name=add_names[0],
                        auto_start=True,
                        target_rtn=outer_f1,
                        app_config=AppConfig.ScriptStyle,
                    )
                ]
                self.build_create_suite(
                    cmd_runner=adder_names[0],
                    f1_create_items=f1_create_items,
                    validate_config=False,
                )
                ########################################################
                # before: lock|req_0_r
                # action: smart_init
                # after:  lock|req_0_r|smart_init_i
                ########################################################
                lm.start_request(adder_names[0], trailing_lock=False)

            ############################################################
            # complete the build in part b
            ############################################################
            self.build_def_del_scenario_part_b(
                lm=lm,
            )

        ################################################################
        # handle expected refresh call
        ################################################################
        if (
            def_del_scenario != DefDelScenario.NormalRecv
            and def_del_scenario != DefDelScenario.NormalWait
            and def_del_scenario != DefDelScenario.ResurrectionRecv
            and def_del_scenario != DefDelScenario.ResurrectionWait
        ):
            pe = self.pending_events[cmd_0_confirmer]
            ref_key: CallRefKey = cmd_0_smart_name

            pe[PE.calling_refresh_msg][ref_key] += 1

            if double_request:
                pe = self.pending_events[cmd_1_confirmer]
                ref_key = cmd_1_smart_name

                pe[PE.calling_refresh_msg][ref_key] += 1

        self.add_cmd(
            ConfirmResponse(
                cmd_runners=[self.commander_name],
                confirm_cmd=cmd_0_name,
                confirm_serial_num=cmd_0_serial_num,
                confirmers=cmd_0_confirmer,
            )
        )

        if cmd_1_name:
            self.add_cmd(
                ConfirmResponse(
                    cmd_runners=[self.commander_name],
                    confirm_cmd=cmd_1_name,
                    confirm_serial_num=cmd_1_serial_num,
                    confirmers=cmd_1_confirmer,
                )
            )

        ################################################################
        # check results
        ################################################################
        self.add_cmd(
            VerifyDefDel(
                cmd_runners=self.commander_name,
                def_del_scenario=def_del_scenario,
                receiver_names=receiver_names,
                sender_names=sender_names,
                waiter_names=waiter_names,
                resumer_names=resumer_names,
                del_names=del_names,
                add_names=add_names,
                deleter_names=deleter_names,
                adder_names=adder_names,
            )
        )

    ####################################################################
    # build_def_del_scenario_part_a
    ####################################################################
    @staticmethod
    def build_def_del_scenario_part_a(
        def_del_scenario: DefDelScenario,
        lm: LockMgr,
    ) -> None:
        """Add ConfigCmd items for a deferred delete.

        Args:
            def_del_scenario: specifies type of test to do
            lm: lock manager class

        """
        ################################################################
        # Upon entry, both requests have been made and are both sitting
        # behind the first lock in _request_setup
        ################################################################

        ################################################################
        # before: lock|request_0a|lock|request_1a|lock
        # action: release lock to allow first smart_recv/wait to
        #         progress to the lock obtain in _request_loop
        # after:  lock|request_1a_s|lock|request_0a_r|lock
        ################################################################
        lm.advance_request()

        ################################################################
        # before: lock|request_1a_s|lock|request_0a_r|lock
        # action: release lock to allow second smart_recv/wait to
        #         progress to the lock obtain in _request_loop.
        # after:  lock|request_0a_r|lock|request_1a_r|lock
        ################################################################
        lm.advance_request()

        ################################################################
        # before: lock|request_0a_r|lock|request_1a_r|lock
        # action: release lock to allow first smart_recv/wait to
        #         progress to the lock obtain before refresh.
        # after:  lock|request_1a_r|lock|request_0a_f|lock
        ################################################################
        lm.advance_request()

        ################################################################
        # before: lock|request_1a_r|lock|request_0a_f|lock
        # action: release lock to allow second smart_recv/wait to
        #         progress to the lock obtain before refresh.
        # after:  lock|request_0a_f|lock|request_1a_f
        ################################################################
        lm.advance_request(trailing_lock=False)

        ################################################################
        # At this point we will have the first cmd behind lock_4 and
        # the second cmd behind the first cmd. We now need to swap the
        # lock positions for some scenarios.
        ################################################################
        if (
            def_del_scenario == DefDelScenario.Recv1Recv0
            or def_del_scenario == DefDelScenario.Wait1Wait0
        ):
            ############################################################
            # before: lock|request_0a_f|lock|request_1a_f
            # action: swap request positions
            # after:  lock|request_1a_f|lock|request_0a_f
            ############################################################
            lm.swap_requestors()

        ################################################################
        # before: lock|request_0a_f|lock|request_1a_f
        # or:     lock|request_1a_f|lock|request_0a_f
        # action: release lock to allow smart_recv/wait to refresh
        # after:  lock|request_1a_f
        # or:     lock|request_0a_f
        ################################################################
        lm.complete_request()

        ################################################################
        # before:  lock|request_1a_f
        # or:      lock|request_0a_f
        # action: release lock to allow final smart_recv/wait to refresh
        # after:  none
        ################################################################
        lm.complete_request()

    ####################################################################
    # build_def_del_scenario_part_b
    ####################################################################
    @staticmethod
    def build_def_del_scenario_part_b(
        lm: LockMgr,
    ) -> None:
        """Add ConfigCmd items for a deferred delete.

        Args:
            lm: lock manager

        """
        ################################################################
        # Upon entry, both requests have been made with request_0
        # sitting behind the lock in _request_loop and request_1, the
        # add or del, sitting respectively behind the lock in register
        # or smart_join
        ################################################################

        ################################################################
        # before:  lock|req_0_r|smart_cmd_c
        # action: release lock to allow request_0 to complete the
        #         request nad then advance to the lock for refresh, and
        #         the add or del will do the refresh ahead of the recv
        #         or wait and complete. The recv or wait will then enter
        #         refresh but find nothing to do (will not produce the
        #         update at UTC message).
        # after:  none
        ################################################################
        lm.complete_request(free_all=True)

    ####################################################################
    # build_recv_msg_timeout_suite
    ####################################################################
    def build_recv_msg_timeout_suite(
        self,
        timeout_type: TimeoutType,
        num_receivers: int,
        num_active_no_delay_senders: int,
        num_active_delay_senders: int,
        num_send_exit_senders: int,
        num_nosend_exit_senders: int,
        num_unreg_senders: int,
        num_reg_senders: int,
    ) -> None:
        """Return a list of ConfigCmd items for a msg timeout.

        Args:
            timeout_type: specifies whether the smart_recv should
                be coded with timeout and whether the smart_recv should
                succeed or fail with a timeout
            num_receivers: number of threads that will do the
                smart_recv
            num_active_no_delay_senders: number of threads that are
                active and will do the smart_send immediately
            num_active_delay_senders: number of threads that are active
                and will do the smart_send after a delay
            num_send_exit_senders: number of threads that are active
                and will do the smart_send and then exit
            num_nosend_exit_senders: number of threads that are
                active and will not do the smart_send and then exit
            num_unreg_senders: number of threads that are
                unregistered and will be created and started and then
                do the smart_send
            num_reg_senders: number of threads that are registered
                and will be started and then do the smart_send

        """
        # Make sure we have enough threads
        assert (
            num_receivers
            + num_active_no_delay_senders
            + num_active_delay_senders
            + num_send_exit_senders
            + num_nosend_exit_senders
            + num_unreg_senders
            + num_reg_senders
        ) <= len(self.unregistered_names)

        assert num_receivers > 0

        assert (
            num_active_no_delay_senders
            + num_active_delay_senders
            + num_send_exit_senders
            + num_nosend_exit_senders
            + num_unreg_senders
            + num_reg_senders
        ) > 0

        if (
            timeout_type == TimeoutType.TimeoutFalse
            or timeout_type == TimeoutType.TimeoutTrue
        ):
            assert (
                num_active_delay_senders
                + num_nosend_exit_senders
                + num_unreg_senders
                + num_reg_senders
            ) > 0

        num_active_needed = (
            num_receivers
            + num_active_no_delay_senders
            + num_active_delay_senders
            + num_send_exit_senders
            + num_nosend_exit_senders
            + 1
        )

        timeout_time = (
            (num_active_no_delay_senders * 0.1)
            + (num_active_delay_senders * 0.1)
            + (num_send_exit_senders * 0.1)
            + (num_nosend_exit_senders * 0.5)
            + (num_unreg_senders * 0.5)
            + (num_reg_senders * 0.5)
        )

        if timeout_type == TimeoutType.TimeoutNone:
            pause_time = 0.5
        elif timeout_type == TimeoutType.TimeoutFalse:
            pause_time = 0.5
            timeout_time = pause_time * 8  # prevent timeout
        else:  # timeout True
            pause_time = timeout_time + 1  # force timeout

        self.build_config(
            cmd_runner=self.commander_name,
            num_registered=num_reg_senders,
            num_active=num_active_needed,
        )

        active_names_copy = self.active_names - {self.commander_name}

        ################################################################
        # choose receiver_names
        ################################################################
        receiver_names = self.choose_names(
            name_collection=active_names_copy,
            num_names_needed=num_receivers,
            update_collection=True,
            var_name_for_log="receiver_names",
        )

        ################################################################
        # choose active_no_delay_sender_names
        ################################################################
        active_no_delay_sender_names = self.choose_names(
            name_collection=active_names_copy,
            num_names_needed=num_active_no_delay_senders,
            update_collection=True,
            var_name_for_log="active_no_delay_sender_names",
        )

        ################################################################
        # choose active_delay_sender_names
        ################################################################
        active_delay_sender_names = self.choose_names(
            name_collection=active_names_copy,
            num_names_needed=num_active_delay_senders,
            update_collection=True,
            var_name_for_log="active_delay_sender_names",
        )

        ################################################################
        # choose send_exit_sender_names
        ################################################################
        send_exit_sender_names = self.choose_names(
            name_collection=active_names_copy,
            num_names_needed=num_send_exit_senders,
            update_collection=True,
            var_name_for_log="send_exit_sender_names",
        )

        ################################################################
        # choose nosend_exit_sender_names
        ################################################################
        nosend_exit_sender_names = self.choose_names(
            name_collection=active_names_copy,
            num_names_needed=num_nosend_exit_senders,
            update_collection=True,
            var_name_for_log="nosend_exit_sender_names",
        )

        ################################################################
        # choose unreg_sender_names
        ################################################################
        unreg_sender_names = self.choose_names(
            name_collection=self.unregistered_names,
            num_names_needed=num_unreg_senders,
            update_collection=False,
            var_name_for_log="unreg_sender_names",
        )

        ################################################################
        # choose reg_sender_names
        ################################################################
        reg_sender_names = self.choose_names(
            name_collection=self.registered_names,
            num_names_needed=num_reg_senders,
            update_collection=False,
            var_name_for_log="reg_sender_names",
        )

        ################################################################
        # start by doing the recv_msgs, one for each sender
        ################################################################
        all_sender_names: list[str] = (
            active_no_delay_sender_names
            + active_delay_sender_names
            + send_exit_sender_names
            + nosend_exit_sender_names
            + unreg_sender_names
            + reg_sender_names
        )

        all_timeout_names: list[str] = (
            active_delay_sender_names
            + send_exit_sender_names
            + nosend_exit_sender_names
            + unreg_sender_names
            + reg_sender_names
        )

        if timeout_type == TimeoutType.TimeoutTrue:
            exp_senders = set(all_sender_names) - set(all_timeout_names)
        else:
            exp_senders = set(all_sender_names) - set(nosend_exit_sender_names)

        if nosend_exit_sender_names:
            exp_senders -= set(unreg_sender_names)
            exp_senders -= set(reg_sender_names)

        self.set_recv_timeout(num_timeouts=len(all_timeout_names) * num_receivers)

        if len(all_sender_names) % 2 == 0:
            log_msg = f"smart_recv log test: {get_ptime()}"
        else:
            log_msg = None

        ################################################################
        # setup the messages to send
        ################################################################
        sender_msgs = SendRecvMsgs(
            sender_names=all_sender_names,
            receiver_names=receiver_names,
            num_msgs=1,
            text="build_recv_msg_timeout_suite",
        )

        if timeout_type == TimeoutType.TimeoutNone:
            confirm_cmd_to_use = "RecvMsg"
            recv_msg_serial_num = self.add_cmd(
                RecvMsg(
                    cmd_runners=receiver_names,
                    senders=all_sender_names,
                    exp_senders=exp_senders,
                    stopped_remotes=nosend_exit_sender_names,
                    exp_msgs=sender_msgs,
                    log_msg=log_msg,
                )
            )
        elif timeout_type == TimeoutType.TimeoutFalse:
            confirm_cmd_to_use = "RecvMsgTimeoutFalse"
            recv_msg_serial_num = self.add_cmd(
                RecvMsgTimeoutFalse(
                    cmd_runners=receiver_names,
                    senders=all_sender_names,
                    exp_senders=exp_senders,
                    stopped_remotes=nosend_exit_sender_names,
                    exp_msgs=sender_msgs,
                    timeout=timeout_time,
                    log_msg=log_msg,
                )
            )

        else:  # TimeoutType.TimeoutTrue
            confirm_cmd_to_use = "RecvMsgTimeoutTrue"
            recv_msg_serial_num = self.add_cmd(
                RecvMsgTimeoutTrue(
                    cmd_runners=receiver_names,
                    senders=all_sender_names,
                    exp_senders=exp_senders,
                    exp_msgs=sender_msgs,
                    timeout=2,
                    timeout_names=all_timeout_names,
                    log_msg=log_msg,
                )
            )

        ################################################################
        # do smart_send from active_no_delay_senders
        ################################################################
        if active_no_delay_sender_names:
            self.add_cmd(
                SendMsg(
                    cmd_runners=active_no_delay_sender_names,
                    receivers=receiver_names,
                    exp_receivers=receiver_names,
                    msgs_to_send=sender_msgs,
                    msg_idx=0,
                )
            )

        self.add_cmd(Pause(cmd_runners=self.commander_name, pause_seconds=pause_time))
        if timeout_type == TimeoutType.TimeoutTrue:
            self.add_cmd(WaitForRecvTimeouts(cmd_runners=self.commander_name))

        ################################################################
        # do smart_send from active_delay_senders
        ################################################################
        if active_delay_sender_names:
            send_serial_num = self.add_cmd(
                SendMsg(
                    cmd_runners=active_delay_sender_names,
                    receivers=receiver_names,
                    exp_receivers=receiver_names,
                    msgs_to_send=sender_msgs,
                    msg_idx=0,
                )
            )
            self.add_cmd(
                ConfirmResponse(
                    cmd_runners=[self.commander_name],
                    confirm_cmd="SendMsg",
                    confirm_serial_num=send_serial_num,
                    confirmers=active_delay_sender_names,
                )
            )

        ################################################################
        # do smart_send from send_exit_senders and then exit
        ################################################################
        if send_exit_sender_names:
            self.add_cmd(
                SendMsg(
                    cmd_runners=send_exit_sender_names,
                    receivers=receiver_names,
                    exp_receivers=receiver_names,
                    msgs_to_send=sender_msgs,
                    msg_idx=0,
                )
            )

            self.build_exit_suite(
                cmd_runner=self.commander_name,
                names=send_exit_sender_names,
                validate_config=False,
            )
            self.build_join_suite(
                cmd_runners=self.commander_name,
                join_target_names=send_exit_sender_names,
                validate_config=False,
            )

        ################################################################
        # exit the nosend_exit_senders, then resurrect and do smart_send
        ################################################################
        if nosend_exit_sender_names:
            # make sure the senders have a chance to complete their
            # sends before we cause the stop from being recognized
            self.add_cmd(
                WaitForCondition(
                    cmd_runners=self.commander_name,
                    check_rtn=self.check_expected_responses,
                    check_args=CheckExpectedResponsesArgs(
                        requestors=set(receiver_names),
                        exp_response_targets=exp_senders,
                        request=st.ReqType.Smart_recv,
                    ),
                )
            )

            self.build_exit_suite(
                cmd_runner=self.commander_name,
                names=nosend_exit_sender_names,
                validate_config=False,
            )
            self.build_join_suite(
                cmd_runners=self.commander_name,
                join_target_names=nosend_exit_sender_names,
                validate_config=False,
            )

            f1_create_items: list[F1CreateItem] = []
            for idx, name in enumerate(nosend_exit_sender_names):
                if idx % 2:
                    app_config = AppConfig.ScriptStyle
                else:
                    app_config = AppConfig.RemoteThreadApp

                f1_create_items.append(
                    F1CreateItem(
                        name=name,
                        auto_start=True,
                        target_rtn=outer_f1,
                        app_config=app_config,
                    )
                )
            self.build_create_suite(
                f1_create_items=f1_create_items, validate_config=False
            )
            self.add_cmd(
                SendMsg(
                    cmd_runners=nosend_exit_sender_names,
                    receivers=receiver_names,
                    exp_receivers=receiver_names,
                    msgs_to_send=sender_msgs,
                    msg_idx=0,
                )
            )

        ################################################################
        # create and start the unreg_senders, then do smart_send
        ################################################################
        if unreg_sender_names:
            f1_create_items = []
            for idx, name in enumerate(unreg_sender_names):
                if idx % 2:
                    app_config = AppConfig.ScriptStyle
                else:
                    app_config = AppConfig.RemoteThreadApp

                f1_create_items.append(
                    F1CreateItem(
                        name=name,
                        auto_start=True,
                        target_rtn=outer_f1,
                        app_config=app_config,
                    )
                )
            self.build_create_suite(
                f1_create_items=f1_create_items, validate_config=False
            )
            self.add_cmd(
                SendMsg(
                    cmd_runners=unreg_sender_names,
                    receivers=receiver_names,
                    exp_receivers=receiver_names,
                    msgs_to_send=sender_msgs,
                    msg_idx=0,
                )
            )

        ################################################################
        # start the reg_senders, then do smart_send
        ################################################################
        if reg_sender_names:
            self.build_start_suite(start_names=reg_sender_names, validate_config=False)
            self.add_cmd(
                SendMsg(
                    cmd_runners=reg_sender_names,
                    receivers=receiver_names,
                    exp_receivers=receiver_names,
                    msgs_to_send=sender_msgs,
                    msg_idx=0,
                )
            )

        ################################################################
        # finally, confirm the smart_recv is done
        ################################################################
        self.add_cmd(
            ConfirmResponse(
                cmd_runners=[self.commander_name],
                confirm_cmd=confirm_cmd_to_use,
                confirm_serial_num=recv_msg_serial_num,
                confirmers=receiver_names,
            )
        )

    ####################################################################
    # build_wait_scenario2
    ####################################################################
    def build_wait_scenario2(
        self, num_waiters: int, num_actors: int, actor_list: list[Actors]
    ) -> None:
        """Adds cmds to the cmd queue.

        Args:
            num_waiters: number of threads that will do the wait
            num_actors: number of threads that will do the resume
            actor_list: contains the actors

        """
        actions: dict[Actors, Callable[..., None]] = {
            Actors.ActiveBeforeActor: self.build_resume_before_wait_timeout_suite,
            Actors.ActiveAfterActor: self.build_resume_after_wait_timeout_suite,
            Actors.ActionExitActor: self.build_resume_exit_wait_timeout_suite,
            Actors.ExitActionActor: self.build_exit_resume_wait_timeout_suite,
            Actors.UnregActor: self.build_unreg_resume_wait_timeout_suite,
            Actors.RegActor: self.build_reg_resume_wait_timeout_suite,
        }
        # Make sure we have enough threads
        assert num_waiters > 0
        assert num_actors > 0
        assert (num_waiters + num_actors) <= len(self.unregistered_names)

        # number needed for waiters, actors, and commander
        num_active_threads_needed = num_waiters + num_actors + 1

        self.build_config(
            cmd_runner=self.commander_name, num_active=num_active_threads_needed
        )

        active_names_copy = self.active_names - {self.commander_name}

        waiter_names = self.choose_names(
            name_collection=active_names_copy,
            num_names_needed=num_waiters,
            update_collection=True,
            var_name_for_log="waiter_names",
        )

        actor_names = self.choose_names(
            name_collection=active_names_copy,
            num_names_needed=num_actors,
            update_collection=True,
            var_name_for_log="actor_names",
        )

        for actor in actor_list:
            actions[actor](waiter_names=waiter_names, actor_names=actor_names)

    # ####################################################################
    # # powerset
    # ####################################################################
    # @staticmethod
    # def powerset(names: list[str]) -> chain[tuple[str, ...]]:
    #     """Returns a generator powerset of the input list of names.
    #
    #     Args:
    #         names: names to use to make a powerset
    #
    #     """
    #     # powerset([1,2,3]) -->
    #     # () (1,) (2,) (3,) (1,2) (1,3) (2,3) (1,2,3)
    #     return chain.from_iterable(
    #         combinations(names, r) for r in range(len(names) + 1)
    #     )
    ####################################################################
    # powerset
    ####################################################################
    @staticmethod
    def powerset(names: list[Any]) -> chain[tuple[Any, ...]]:
        """Returns a generator powerset of the input list of names.

        Args:
            names: names to use to make a powerset

        """
        # powerset([1,2,3]) -->
        # () (1,) (2,) (3,) (1,2) (1,3) (2,3) (1,2,3)
        return chain.from_iterable(
            combinations(names, r) for r in range(len(names) + 1)
        )

    ####################################################################
    # build_wait_active_suite
    ####################################################################
    def build_resume_before_wait_timeout_suite(
        self, waiter_names: list[str], actor_names: list[str]
    ) -> None:
        """Adds cmds to the cmd queue.

        Args:
            waiter_names: names of threads that will do the wait
            actor_names: names of threads that will do the resume

        """
        ################################################################
        # Loop to do combinations of resume names, the waiter names that
        # will be resumed - the remaining waiter names will timeout
        ################################################################
        for target_names in self.powerset(waiter_names.copy()):
            timeout_names = waiter_names
            if target_names:
                # target_names = list(target_names)
                ########################################################
                # resume the waiters that are expected to succeed
                ########################################################
                resume_cmd_serial_num = self.add_cmd(
                    Resume(
                        cmd_runners=actor_names,
                        targets=target_names,
                        exp_resumed_targets=target_names,
                        stopped_remotes=[],
                    )
                )
                self.add_cmd(
                    ConfirmResponse(
                        cmd_runners=[self.commander_name],
                        confirm_cmd="Resume",
                        confirm_serial_num=resume_cmd_serial_num,
                        confirmers=actor_names,
                    )
                )

                timeout_time = 1.5
                wait_serial_num = self.add_cmd(
                    WaitTimeoutFalse(
                        cmd_runners=target_names,
                        resumers=actor_names,
                        exp_resumers=actor_names,
                        stopped_remotes=set(),
                        timeout=timeout_time,
                    )
                )

                self.add_cmd(
                    ConfirmResponse(
                        cmd_runners=[self.commander_name],
                        confirm_cmd="WaitTimeoutFalse",
                        confirm_serial_num=wait_serial_num,
                        confirmers=target_names,
                    )
                )

                timeout_names = list(set(waiter_names) - set(target_names))

            if timeout_names:
                ########################################################
                # the timeout_names are expected to timeout since they
                # were not resumed
                ########################################################
                timeout_time = 0.5
                wait_serial_num = self.add_cmd(
                    WaitTimeoutTrue(
                        cmd_runners=timeout_names,
                        resumers=actor_names,
                        exp_resumers=set(),
                        stopped_remotes=set(),
                        timeout=timeout_time,
                        timeout_remotes=set(actor_names),
                    )
                )

                self.add_cmd(
                    ConfirmResponse(
                        cmd_runners=[self.commander_name],
                        confirm_cmd="WaitTimeoutTrue",
                        confirm_serial_num=wait_serial_num,
                        confirmers=timeout_names,
                    )
                )

    ####################################################################
    # build_wait_active_suite
    ####################################################################
    def build_resume_after_wait_timeout_suite(
        self, waiter_names: list[str], actor_names: list[str]
    ) -> None:
        """Adds cmds to the cmd queue.

        Args:
            waiter_names: names of threads that will do the wait
            actor_names: names of threads that will do the resume

        """
        ################################################################
        # Loop to do combinations of resume names, the waiter names that
        # will be resumed - the remaining waiter names will timeout
        ################################################################
        for target_names in self.powerset(waiter_names.copy()):
            timeout_names = waiter_names
            if target_names:
                ########################################################
                # resume the waiters that are expected to succeed
                ########################################################
                timeout_time = 1.5
                wait_serial_num = self.add_cmd(
                    WaitTimeoutFalse(
                        cmd_runners=list(target_names),
                        resumers=actor_names,
                        exp_resumers=actor_names,
                        stopped_remotes=set(),
                        timeout=timeout_time,
                    )
                )

                resume_cmd_serial_num = self.add_cmd(
                    Resume(
                        cmd_runners=actor_names,
                        targets=list(target_names),
                        exp_resumed_targets=list(target_names),
                        stopped_remotes=[],
                    )
                )
                self.add_cmd(
                    ConfirmResponse(
                        cmd_runners=[self.commander_name],
                        confirm_cmd="Resume",
                        confirm_serial_num=resume_cmd_serial_num,
                        confirmers=actor_names,
                    )
                )

                self.add_cmd(
                    ConfirmResponse(
                        cmd_runners=[self.commander_name],
                        confirm_cmd="WaitTimeoutFalse",
                        confirm_serial_num=wait_serial_num,
                        confirmers=list(target_names),
                    )
                )

                timeout_names = list(set(waiter_names) - set(target_names))

            if timeout_names:
                ########################################################
                # the timeout_names are expected to timeout since they
                # were not resumed
                ########################################################
                timeout_time = 0.5
                wait_serial_num = self.add_cmd(
                    WaitTimeoutTrue(
                        cmd_runners=timeout_names,
                        resumers=actor_names,
                        exp_resumers=set(),
                        stopped_remotes=set(),
                        timeout=timeout_time,
                        timeout_remotes=set(actor_names),
                    )
                )
                self.add_cmd(
                    ConfirmResponse(
                        cmd_runners=[self.commander_name],
                        confirm_cmd="WaitTimeoutTrue",
                        confirm_serial_num=wait_serial_num,
                        confirmers=timeout_names,
                    )
                )

    ####################################################################
    # build_wait_active_suite
    ####################################################################
    def build_resume_exit_wait_timeout_suite(
        self, waiter_names: list[str], actor_names: list[str]
    ) -> None:
        """Adds cmds to the cmd queue.

        Args:
            waiter_names: names of threads that will do the wait
            actor_names: names of threads that will do the resume

        """
        ################################################################
        # Loop to do combinations of resume names, the waiter names that
        # will be resumed - the remaining waiter names will timeout
        ################################################################
        for target_names in self.powerset(waiter_names.copy()):
            timeout_names = waiter_names
            if target_names:
                # target_names = list(target_names)
                ########################################################
                # resume the waiters that are expected to succeed
                ########################################################
                resume_cmd_serial_num = self.add_cmd(
                    Resume(
                        cmd_runners=actor_names,
                        targets=target_names,
                        exp_resumed_targets=target_names,
                        stopped_remotes=[],
                    )
                )

                self.add_cmd(
                    ConfirmResponse(
                        cmd_runners=[self.commander_name],
                        confirm_cmd="Resume",
                        confirm_serial_num=resume_cmd_serial_num,
                        confirmers=actor_names,
                    )
                )

                self.build_exit_suite(cmd_runner=self.commander_name, names=actor_names)
                self.build_join_suite(
                    cmd_runners=self.commander_name, join_target_names=actor_names
                )

                for resumer_name in actor_names:
                    self.add_cmd(
                        VerifyConfig(
                            cmd_runners=self.commander_name,
                            verify_type=VerifyType.VerifyHalfPaired,
                            names_to_check=target_names,
                            aux_names=resumer_name,
                        )
                    )

                timeout_time = 1.5
                wait_serial_num = self.add_cmd(
                    WaitTimeoutFalse(
                        cmd_runners=target_names,
                        resumers=actor_names,
                        exp_resumers=actor_names,
                        stopped_remotes=set(),
                        timeout=timeout_time,
                    )
                )
                self.add_cmd(
                    ConfirmResponse(
                        cmd_runners=[self.commander_name],
                        confirm_cmd="WaitTimeoutFalse",
                        confirm_serial_num=wait_serial_num,
                        confirmers=target_names,
                    )
                )

                f1_create_items: list[F1CreateItem] = []
                for idx, name in enumerate(actor_names):
                    if idx % 2:
                        app_config = AppConfig.ScriptStyle
                    else:
                        app_config = AppConfig.RemoteThreadApp

                    f1_create_items.append(
                        F1CreateItem(
                            name=name,
                            auto_start=True,
                            target_rtn=outer_f1,
                            app_config=app_config,
                        )
                    )
                self.build_create_suite(
                    f1_create_items=f1_create_items, validate_config=False
                )

                timeout_names = list(set(waiter_names) - set(target_names))

            if timeout_names:
                ########################################################
                # the timeout_names are expected to timeout since they
                # were not resumed
                ########################################################
                timeout_time = 0.5
                wait_serial_num = self.add_cmd(
                    WaitTimeoutTrue(
                        cmd_runners=timeout_names,
                        resumers=actor_names,
                        exp_resumers=set(),
                        stopped_remotes=set(),
                        timeout=timeout_time,
                        timeout_remotes=set(actor_names),
                    )
                )
                self.add_cmd(
                    ConfirmResponse(
                        cmd_runners=[self.commander_name],
                        confirm_cmd="WaitTimeoutTrue",
                        confirm_serial_num=wait_serial_num,
                        confirmers=timeout_names,
                    )
                )

    ####################################################################
    # build_exit_resume_wait_timeout_suite
    ####################################################################
    def build_exit_resume_wait_timeout_suite(
        self, waiter_names: list[str], actor_names: list[str]
    ) -> None:
        """Adds cmds to the cmd queue.

        Args:
            waiter_names: names of threads that will do the wait
            actor_names: names of threads that will do the resume

        """
        ################################################################
        # Loop to do combinations of resume names, the waiter names that
        # will be resumed - the remaining waiter names will timeout
        ################################################################
        for target_names in self.powerset(waiter_names.copy()):
            timeout_names = waiter_names

            if len(target_names) % 2:
                stopped_remotes = set(actor_names.copy())
                exp_resumers = set()
            else:
                stopped_remotes = set()
                exp_resumers = set(actor_names.copy())

            if target_names:
                # target_names = list(target_names)

                timeout_time = 3.0
                wait_serial_num = self.add_cmd(
                    WaitTimeoutFalse(
                        cmd_runners=target_names,
                        resumers=actor_names,
                        exp_resumers=exp_resumers,
                        stopped_remotes=stopped_remotes,
                        timeout=timeout_time,
                    )
                )

                if stopped_remotes:
                    self.build_exit_suite(
                        cmd_runner=self.commander_name, names=actor_names
                    )

                    self.add_cmd(
                        ConfirmResponse(
                            cmd_runners=[self.commander_name],
                            confirm_cmd="WaitTimeoutFalse",
                            confirm_serial_num=wait_serial_num,
                            confirmers=target_names,
                        )
                    )

                    self.build_join_suite(
                        cmd_runners=self.commander_name, join_target_names=actor_names
                    )

                    f1_create_items: list[F1CreateItem] = []
                    for idx, name in enumerate(actor_names):
                        if idx % 2:
                            app_config = AppConfig.ScriptStyle
                        else:
                            app_config = AppConfig.RemoteThreadApp

                        f1_create_items.append(
                            F1CreateItem(
                                name=name,
                                auto_start=True,
                                target_rtn=outer_f1,
                                app_config=app_config,
                            )
                        )
                    self.build_create_suite(
                        f1_create_items=f1_create_items, validate_config=False
                    )

                if not stopped_remotes:
                    ####################################################
                    # resume the waiters that are expected to succeed
                    ####################################################
                    resume_cmd_serial_num = self.add_cmd(
                        Resume(
                            cmd_runners=actor_names,
                            targets=target_names,
                            exp_resumed_targets=target_names,
                            stopped_remotes=[],
                        )
                    )

                    self.add_cmd(
                        ConfirmResponse(
                            cmd_runners=[self.commander_name],
                            confirm_cmd="Resume",
                            confirm_serial_num=resume_cmd_serial_num,
                            confirmers=actor_names,
                        )
                    )

                    self.add_cmd(
                        ConfirmResponse(
                            cmd_runners=[self.commander_name],
                            confirm_cmd="WaitTimeoutFalse",
                            confirm_serial_num=wait_serial_num,
                            confirmers=target_names,
                        )
                    )

                timeout_names = list(set(waiter_names) - set(target_names))

            if timeout_names:
                ########################################################
                # the timeout_names are expected to timeout since they
                # were not resumed
                ########################################################
                if len(timeout_names) % 2:
                    stopped_remotes = set(actor_names.copy())
                    self.build_exit_suite(
                        cmd_runner=self.commander_name, names=actor_names
                    )
                else:
                    stopped_remotes = set()

                timeout_time = 0.5
                wait_serial_num = self.add_cmd(
                    WaitTimeoutTrue(
                        cmd_runners=timeout_names,
                        resumers=actor_names,
                        exp_resumers=set(),
                        stopped_remotes=stopped_remotes,
                        timeout=timeout_time,
                        timeout_remotes=set(actor_names),
                    )
                )
                self.add_cmd(
                    ConfirmResponse(
                        cmd_runners=[self.commander_name],
                        confirm_cmd="WaitTimeoutTrue",
                        confirm_serial_num=wait_serial_num,
                        confirmers=timeout_names,
                    )
                )
                if stopped_remotes:
                    self.build_join_suite(
                        cmd_runners=self.commander_name, join_target_names=actor_names
                    )

                    f1_create_items = []
                    for idx, name in enumerate(actor_names):
                        if idx % 2:
                            app_config = AppConfig.ScriptStyle
                        else:
                            app_config = AppConfig.RemoteThreadApp

                        f1_create_items.append(
                            F1CreateItem(
                                name=name,
                                auto_start=True,
                                target_rtn=outer_f1,
                                app_config=app_config,
                            )
                        )
                    self.build_create_suite(
                        f1_create_items=f1_create_items, validate_config=False
                    )

    ####################################################################
    # build_wait_active_suite
    ####################################################################
    def build_unreg_resume_wait_timeout_suite(
        self, waiter_names: list[str], actor_names: list[str]
    ) -> None:
        """Adds cmds to the cmd queue.

        Args:
            waiter_names: names of threads that will do the wait
            actor_names: names of threads that will do the resume

        """
        ################################################################
        # Loop to do combinations of resume names, the waiter names that
        # will be resumed - the remaining waiter names will timeout
        ################################################################
        for target_names in self.powerset(waiter_names.copy()):
            if target_names:
                # target_names = list(target_names)

                ########################################################
                # get actors into unreg state
                ########################################################
                self.build_exit_suite(cmd_runner=self.commander_name, names=actor_names)
                self.build_join_suite(
                    cmd_runners=self.commander_name, join_target_names=actor_names
                )

                ########################################################
                # do the wait
                ########################################################
                wait_serial_num = self.add_cmd(
                    Wait(
                        cmd_runners=target_names,
                        resumers=actor_names,
                        exp_resumers=actor_names,
                        stopped_remotes=set(),
                    )
                )

                ########################################################
                # get actors into active state
                ########################################################
                f1_create_items: list[F1CreateItem] = []
                for idx, name in enumerate(actor_names):
                    if idx % 2:
                        app_config = AppConfig.ScriptStyle
                    else:
                        app_config = AppConfig.RemoteThreadApp

                    f1_create_items.append(
                        F1CreateItem(
                            name=name,
                            auto_start=True,
                            target_rtn=outer_f1,
                            app_config=app_config,
                        )
                    )
                self.build_create_suite(
                    f1_create_items=f1_create_items, validate_config=False
                )

                ########################################################
                # resume the waiters
                ########################################################
                resume_cmd_serial_num = self.add_cmd(
                    Resume(
                        cmd_runners=actor_names,
                        targets=target_names,
                        exp_resumed_targets=target_names,
                        stopped_remotes=[],
                    )
                )

                self.add_cmd(
                    ConfirmResponse(
                        cmd_runners=[self.commander_name],
                        confirm_cmd="Resume",
                        confirm_serial_num=resume_cmd_serial_num,
                        confirmers=actor_names,
                    )
                )

                self.add_cmd(
                    ConfirmResponse(
                        cmd_runners=[self.commander_name],
                        confirm_cmd="Wait",
                        confirm_serial_num=wait_serial_num,
                        confirmers=target_names,
                    )
                )

    ####################################################################
    # build_wait_active_suite
    ####################################################################
    def build_reg_resume_wait_timeout_suite(
        self, waiter_names: list[str], actor_names: list[str]
    ) -> None:
        """Adds cmds to the cmd queue.

        Args:
            waiter_names: names of threads that will do the wait
            actor_names: names of threads that will do the resume

        """
        ################################################################
        # Loop to do combinations of resume names, the waiter names that
        # will be resumed - the remaining waiter names will timeout
        ################################################################
        for target_names in self.powerset(waiter_names.copy()):
            if target_names:
                ########################################################
                # get actors into reg state
                ########################################################
                self.build_exit_suite(cmd_runner=self.commander_name, names=actor_names)
                self.build_join_suite(
                    cmd_runners=self.commander_name, join_target_names=actor_names
                )

                f1_create_items: list[F1CreateItem] = []
                for idx, name in enumerate(actor_names):
                    if idx % 2:
                        app_config = AppConfig.ScriptStyle
                    else:
                        app_config = AppConfig.RemoteThreadApp

                    f1_create_items.append(
                        F1CreateItem(
                            name=name,
                            auto_start=False,
                            target_rtn=outer_f1,
                            app_config=app_config,
                        )
                    )
                self.build_create_suite(
                    f1_create_items=f1_create_items, validate_config=False
                )

                ########################################################
                # do the wait
                ########################################################
                wait_serial_num = self.add_cmd(
                    Wait(
                        cmd_runners=target_names,
                        resumers=actor_names,
                        exp_resumers=actor_names,
                        stopped_remotes=set(),
                    )
                )

                ########################################################
                # get actors into active state
                ########################################################
                self.build_start_suite(start_names=actor_names)

                ########################################################
                # resume the waiters
                ########################################################
                resume_cmd_serial_num = self.add_cmd(
                    Resume(
                        cmd_runners=actor_names,
                        targets=target_names,
                        exp_resumed_targets=target_names,
                        stopped_remotes=[],
                    )
                )

                self.add_cmd(
                    ConfirmResponse(
                        cmd_runners=[self.commander_name],
                        confirm_cmd="Resume",
                        confirm_serial_num=resume_cmd_serial_num,
                        confirmers=actor_names,
                    )
                )

                self.add_cmd(
                    ConfirmResponse(
                        cmd_runners=[self.commander_name],
                        confirm_cmd="Wait",
                        confirm_serial_num=wait_serial_num,
                        confirmers=target_names,
                    )
                )

    ####################################################################
    # build_resume_scenario
    ####################################################################
    def build_resume_scenario(
        self,
        num_resumers: int,
        num_start_before: int,
        num_unreg_before: int,
        num_stop_before: int,
        num_unreg_after: int,
        num_stop_after_ok: int,
        num_stop_after_err: int,
    ) -> None:
        """Test meta configuration scenarios.

        Args:
            num_resumers: number of threads doing resumes
            num_start_before: number of target_rtn threads that will
                be started and issue a wait before the resume is done,
                and should succeed
            num_unreg_before: number of target_rtn threads that will be
                registered and then unregistered before the resume, and
                then started after the resume, and should succeed
            num_stop_before: number of target_rtn threads that will
                be started and then stopped (but not joined) before the
                resume, and should result in a not alive error
            num_unreg_after: number of target_rtn threads that will be
                unregistered after the resume, and should cause an error
            num_stop_after_ok: number of target_rtn threads that will
                be started after the resume is issued, and will stay
                alive long enough for the resume to set the wait_flag,
                and will then be stopped and joined, and should result
                in success
            num_stop_after_err: number of target_rtn threads that will
                be started after the resume is issued, and will quickly
                be stopped and joined before the resume has a chance to
                see that is is alive to set the wait_flag, and should
                result in a not alive error

        """
        # Make sure we have enough threads
        total_arg_counts = (
            num_resumers
            + num_start_before
            + num_unreg_before
            + num_stop_before
            + num_unreg_after
            + num_stop_after_ok
            + num_stop_after_err
        )
        assert total_arg_counts <= len(self.unregistered_names)

        assert num_resumers > 0

        num_active_needed = num_resumers + 1  # plus 1 for commander

        self.build_config(
            cmd_runner=self.commander_name,
            num_active=num_active_needed,
        )

        # remove commander
        active_names_copy = self.active_names - {self.commander_name}

        ################################################################
        # choose resumer_names
        ################################################################
        resumer_names = self.choose_names(
            name_collection=active_names_copy,
            num_names_needed=num_resumers,
            update_collection=True,
            var_name_for_log="resumer_names",
        )

        ################################################################
        # choose start_before_names
        ################################################################
        unregistered_names_copy = self.unregistered_names.copy()
        start_before_names = self.choose_names(
            name_collection=unregistered_names_copy,
            num_names_needed=num_start_before,
            update_collection=True,
            var_name_for_log="start_before_names",
        )

        ################################################################
        # choose unreg_before_names
        ################################################################
        unreg_before_names = self.choose_names(
            name_collection=unregistered_names_copy,
            num_names_needed=num_unreg_before,
            update_collection=True,
            var_name_for_log="unreg_before_names",
        )

        ################################################################
        # choose stop_before_names
        ################################################################
        stop_before_names = self.choose_names(
            name_collection=unregistered_names_copy,
            num_names_needed=num_stop_before,
            update_collection=True,
            var_name_for_log="stop_before_names",
        )

        ################################################################
        # choose unreg_after_names
        ################################################################
        unreg_after_names = self.choose_names(
            name_collection=unregistered_names_copy,
            num_names_needed=num_unreg_after,
            update_collection=True,
            var_name_for_log="unreg_after_names",
        )

        ################################################################
        # choose stop_after_ok_names
        ################################################################
        stop_after_ok_names = self.choose_names(
            name_collection=unregistered_names_copy,
            num_names_needed=num_stop_after_ok,
            update_collection=True,
            var_name_for_log="stop_after_ok_names",
        )

        ################################################################
        # choose stop_after_err_names
        ################################################################
        stop_after_err_names = self.choose_names(
            name_collection=unregistered_names_copy,
            num_names_needed=num_stop_after_err,
            update_collection=True,
            var_name_for_log="stop_after_err_names",
        )

        all_targets: list[str] = (
            start_before_names
            + unreg_before_names
            + stop_before_names
            + unreg_after_names
            + stop_after_ok_names
            + stop_after_err_names
        )

        after_targets: list[str] = (
            unreg_before_names
            + unreg_after_names
            + stop_after_ok_names
            + stop_after_err_names
        )

        ################################################################
        # monkeypatch for SmartThread._get_target_state
        ################################################################
        a_target_mock_dict = {}
        if stop_after_err_names:
            for resumer_name in resumer_names:
                a_sub_dict = {}
                for stop_name in stop_after_err_names:
                    a_sub_dict[stop_name] = (
                        st.ThreadState.Alive,
                        st.ThreadState.Registered,
                    )
                a_target_mock_dict[resumer_name] = a_sub_dict

        MockGetTargetState(targets=a_target_mock_dict, config_ver=self)

        resume_serial_num_2 = 0

        wait_confirms: list[ConfirmResponse] = []
        for idx, waiter in enumerate(
            roundrobin(start_before_names, unreg_before_names, stop_before_names)
        ):
            if idx % 2:
                app_config = AppConfig.ScriptStyle
            else:
                app_config = AppConfig.RemoteThreadApp

            if waiter in start_before_names:
                self.build_create_suite(
                    f1_create_items=[
                        F1CreateItem(
                            name=waiter,
                            auto_start=True,
                            target_rtn=outer_f1,
                            app_config=app_config,
                        )
                    ],
                    validate_config=False,
                )
                wait_serial_num = self.add_cmd(
                    Wait(
                        cmd_runners=waiter,
                        resumers=resumer_names,
                        exp_resumers=resumer_names,
                    )
                )
                wait_confirms.append(
                    ConfirmResponse(
                        cmd_runners=[self.commander_name],
                        confirm_cmd="Wait",
                        confirm_serial_num=wait_serial_num,
                        confirmers=waiter,
                    )
                )
            elif waiter in unreg_before_names:
                self.build_create_suite(
                    f1_create_items=[
                        F1CreateItem(
                            name=waiter,
                            auto_start=False,
                            target_rtn=outer_f1,
                            app_config=app_config,
                        )
                    ],
                    validate_config=False,
                )
                self.build_unreg_suite(names=waiter)
            elif waiter in stop_before_names:
                self.build_create_suite(
                    f1_create_items=[
                        F1CreateItem(
                            name=waiter,
                            auto_start=True,
                            target_rtn=outer_f1,
                            app_config=app_config,
                        )
                    ],
                    validate_config=False,
                )
                # stop now, join later
                self.build_exit_suite(
                    cmd_runner=self.commander_name, names=waiter, validate_config=False
                )
            else:
                raise IncorrectDataDetected(
                    "build_resume_scenario "
                    f"{waiter=} not found in "
                    f"{start_before_names=} nor "
                    f"{unreg_before_names=} nor "
                    f"{stop_before_names=}"
                )

        ################################################################
        # wait for wait to be running and waiting to be resumed
        ################################################################
        if start_before_names:
            self.add_cmd(
                WaitForRequestTimeouts(
                    cmd_runners=self.commander_name,
                    actor_names=start_before_names,
                    timeout_names=resumer_names,
                )
            )
        ################################################################
        # issue smart_resume
        ################################################################
        if stop_before_names:
            stopped_remotes = stop_before_names
            exp_resumed_targets = set(start_before_names)
        else:
            exp_resumed_targets = (
                set(start_before_names)
                | set(unreg_before_names)
                | set(stop_after_ok_names)
            )
            stopped_remotes = unreg_after_names + stop_after_err_names

        resume_serial_num_1 = self.add_cmd(
            Resume(
                cmd_runners=resumer_names,
                targets=all_targets,
                exp_resumed_targets=exp_resumed_targets,
                stopped_remotes=stopped_remotes,
            )
        )

        ################################################################
        # confirm response now if we should have raised error for
        # stopped remotes
        ################################################################
        if stop_before_names:
            self.add_cmd(
                ConfirmResponse(
                    cmd_runners=[self.commander_name],
                    confirm_cmd="Resume",
                    confirm_serial_num=resume_serial_num_1,
                    confirmers=resumer_names,
                )
            )
            ############################################################
            # we need this resume for the after resume waits when the
            # first resume ends early because of stopped remotes
            ############################################################
            if after_targets:
                stopped_remotes = unreg_after_names + stop_after_err_names
                exp_resumed_targets = set(unreg_before_names) | set(stop_after_ok_names)
                resume_serial_num_2 = self.add_cmd(
                    Resume(
                        cmd_runners=resumer_names,
                        targets=after_targets,
                        exp_resumed_targets=exp_resumed_targets,
                        stopped_remotes=stopped_remotes,
                    )
                )

        ################################################################
        # Create and start unreg_before and stop_after_ok and issue the
        # wait. Note unreg_before is used both before and after the
        # resume
        ################################################################
        for idx, waiter in enumerate(
            roundrobin(unreg_before_names, stop_after_ok_names)
        ):
            if idx % 2:
                app_config = AppConfig.ScriptStyle
            else:
                app_config = AppConfig.RemoteThreadApp

            self.build_create_suite(
                f1_create_items=[
                    F1CreateItem(
                        name=waiter,
                        auto_start=True,
                        target_rtn=outer_f1,
                        app_config=app_config,
                    )
                ],
                validate_config=False,
            )
            wait_serial_num = self.add_cmd(
                Wait(
                    cmd_runners=waiter,
                    resumers=resumer_names,
                    exp_resumers=resumer_names,
                )
            )
            wait_confirms.append(
                ConfirmResponse(
                    cmd_runners=[self.commander_name],
                    confirm_cmd="Wait",
                    confirm_serial_num=wait_serial_num,
                    confirmers=waiter,
                )
            )

        ################################################################
        # build unreg_after and stop_after_err
        ################################################################
        for idx, waiter in enumerate(
            roundrobin(unreg_after_names, stop_after_err_names)
        ):
            if idx % 2:
                app_config = AppConfig.ScriptStyle
            else:
                app_config = AppConfig.RemoteThreadApp

            if waiter in unreg_after_names:
                self.build_create_suite(
                    f1_create_items=[
                        F1CreateItem(
                            name=waiter,
                            auto_start=False,
                            target_rtn=outer_f1,
                            app_config=app_config,
                        )
                    ],
                    validate_config=False,
                )
                self.build_unreg_suite(names=waiter)
            elif waiter in stop_after_err_names:
                self.build_create_suite(
                    f1_create_items=[
                        F1CreateItem(
                            name=waiter,
                            auto_start=True,
                            target_rtn=outer_f1,
                            app_config=app_config,
                        )
                    ],
                    validate_config=False,
                )
                self.build_exit_suite(
                    cmd_runner=self.commander_name, names=waiter, validate_config=False
                )
                self.build_join_suite(
                    cmd_runners=self.commander_name,
                    join_target_names=waiter,
                    validate_config=False,
                )
            else:
                raise IncorrectDataDetected(
                    "build_resume_scenario "
                    f"{waiter=} not found in "
                    f"{unreg_after_names=} nor "
                    f"{stop_after_err_names=}"
                )

        ####################################################
        # confirm the resumes
        ####################################################
        if not stop_before_names:
            self.add_cmd(
                ConfirmResponse(
                    cmd_runners=[self.commander_name],
                    confirm_cmd="Resume",
                    confirm_serial_num=resume_serial_num_1,
                    confirmers=resumer_names,
                )
            )
        elif after_targets:
            self.add_cmd(
                ConfirmResponse(
                    cmd_runners=[self.commander_name],
                    confirm_cmd="Resume",
                    confirm_serial_num=resume_serial_num_2,
                    confirmers=resumer_names,
                )
            )

        for confirm in wait_confirms:
            self.add_cmd(confirm)

    ####################################################################
    # build_srrw_scenario
    ####################################################################
    def build_srrw_scenario(
        self,
        req_type: st.ReqType,
        num_requestors: int,
        num_start_before: int,
        num_unreg_before: int,
        num_stop_before: int,
        num_unreg_after: int,
        num_stop_after_ok: int,
        num_stop_after_err: int,
    ) -> None:
        """Test meta configuration scenarios.

        Args:
            req_type: specifies whether to issue resume or wait
            num_requestors: number of threads doing resume/wait
            num_start_before: number of target_rtn threads that will
                be started and issue a wait/resume before the resume is
                done, and should succeed
            num_unreg_before: number of target_rtn threads that will be
                registered and then unregistered before the resume/wait,
                and then started after the resume/wait, and should
                succeed
            num_stop_before: number of target_rtn threads that will
                be started and then stopped (but not joined) before the
                resume, and should result in a not alive error
            num_unreg_after: number of target_rtn threads that will be
                unregistered after the resume, and should cause an error
            num_stop_after_ok: number of target_rtn threads that will
                be started after the resume is issued, and will stay
                alive long enough for the resume to set the wait_flag,
                and will then be stopped and joined, and should result
                in success
            num_stop_after_err: number of target_rtn threads that will
                be started after the resume is issued, and will quickly
                be stopped and joined before the resume has a chance to
                see that is is alive to set the wait_flag, and should
                result in a not alive error

        """
        # Make sure we have enough threads
        total_arg_counts = (
            num_requestors
            + num_start_before
            + num_unreg_before
            + num_stop_before
            + num_unreg_after
            + num_stop_after_ok
            + num_stop_after_err
        )
        assert total_arg_counts <= len(self.unregistered_names)

        assert num_requestors > 0

        requestors = get_names("requestor_", num_requestors)
        start_before_names = get_names("start_before_", num_start_before)
        unreg_before_names = get_names("unreg_before_", num_unreg_before)
        stop_before_names = get_names("stop_before_", num_stop_before)
        unreg_after_names = get_names("unreg_after_", num_unreg_after)
        stop_after_ok_names = get_names("stop_after_ok_", num_stop_after_ok)
        stop_after_err_names = get_names("stop_after_err_", num_stop_after_err)

        all_targets: set[str] = (
            start_before_names
            | unreg_before_names
            | stop_before_names
            | unreg_after_names
            | stop_after_ok_names
            | stop_after_err_names
        )

        after_targets: set[str] = (
            unreg_before_names
            | unreg_after_names
            | stop_after_ok_names
            | stop_after_err_names
        )

        self.create_config(unreg_names=all_targets, active_names=requestors)

        ################################################################
        # monkeypatch for SmartThread._get_target_state
        ################################################################
        a_target_mock_dict = {}
        if stop_after_err_names:
            for requestor_name in requestors:
                a_sub_dict = {}
                for stop_name in stop_after_err_names:
                    a_sub_dict[stop_name] = (
                        st.ThreadState.Alive,
                        st.ThreadState.Registered,
                    )
                a_target_mock_dict[requestor_name] = a_sub_dict

        MockGetTargetState(targets=a_target_mock_dict, config_ver=self)

        ################################################################
        # msgs_to_send
        ################################################################
        msgs_to_send = SendRecvMsgs(
            sender_names=requestors | all_targets,
            receiver_names=requestors | all_targets,
            num_msgs=1,
            text="build_srrw_scenario",
        )

        ################################################################
        # build_send_request
        ################################################################
        def build_send_request(
            cmd_runners: Iterable[str],
            targets: Iterable[str],
            exp_targets: Iterable[str],
            stopped_targets: Optional[Iterable[str]] = None,
        ) -> tuple[str, int]:
            """Add send request to run scenario."""
            request_to_confirm = "SendMsg"
            request_serial_num = self.add_cmd(
                SendMsg(
                    cmd_runners=cmd_runners,
                    receivers=targets,
                    exp_receivers=exp_targets,
                    stopped_remotes=stopped_targets,
                    msgs_to_send=msgs_to_send,
                    msg_idx=0,
                )
            )

            return request_to_confirm, request_serial_num

        ################################################################
        # build_receive_request
        ################################################################
        def build_recv_request(
            cmd_runners: Iterable[str],
            targets: Iterable[str],
            exp_targets: Iterable[str],
            stopped_targets: Optional[Iterable[str]] = None,
        ) -> tuple[str, int]:
            """Add receive request to run scenario."""
            request_to_confirm = "RecvMsg"
            request_serial_num = self.add_cmd(
                RecvMsg(
                    cmd_runners=cmd_runners,
                    senders=targets,
                    exp_senders=exp_targets,
                    stopped_remotes=stopped_targets,
                    exp_msgs=msgs_to_send,
                )
            )
            return request_to_confirm, request_serial_num

        ################################################################
        # build_resume_request
        ################################################################
        def build_resume_request(
            cmd_runners: Iterable[str],
            targets: Iterable[str],
            exp_targets: Iterable[str],
            stopped_targets: Optional[Iterable[str]] = None,
        ) -> tuple[str, int]:
            """Add send request to run scenario."""
            request_to_confirm = "Resume"
            request_serial_num = self.add_cmd(
                Resume(
                    cmd_runners=cmd_runners,
                    targets=targets,
                    exp_resumed_targets=exp_targets,
                    stopped_remotes=stopped_targets,
                )
            )
            return request_to_confirm, request_serial_num

        ################################################################
        # build_wait_request
        ################################################################
        def build_wait_request(
            cmd_runners: Iterable[str],
            targets: Iterable[str],
            exp_targets: Iterable[str],
            stopped_targets: Optional[Iterable[str]] = None,
        ) -> tuple[str, int]:
            """Add wait request to run scenario."""
            request_to_confirm = "Wait"
            request_serial_num = self.add_cmd(
                Wait(
                    cmd_runners=cmd_runners,
                    resumers=targets,
                    exp_resumers=exp_targets,
                    stopped_remotes=stopped_targets,
                )
            )
            return request_to_confirm, request_serial_num

        ################################################################
        # request_builds table
        ################################################################
        request_builds: dict[st.ReqType, Callable[..., tuple[str, int]]] = {
            st.ReqType.Smart_send: build_send_request,
            st.ReqType.Smart_recv: build_recv_request,
            st.ReqType.Smart_resume: build_resume_request,
            st.ReqType.Smart_wait: build_wait_request,
        }

        ################################################################
        # target_builds table
        ################################################################
        target_builds: dict[st.ReqType, Callable[..., tuple[str, int]]] = {
            st.ReqType.Smart_send: build_recv_request,
            st.ReqType.Smart_recv: build_send_request,
            st.ReqType.Smart_resume: build_wait_request,
            st.ReqType.Smart_wait: build_resume_request,
        }

        confirm_req_1 = ""
        confirm_serial_1 = 0
        target_confirms_before: list[ConfirmResponse] = []
        target_confirms_after: list[ConfirmResponse] = []

        ################################################################
        # First batch of targets for start, unreg, and stop before
        ################################################################
        for idx, target in enumerate(
            roundrobin(start_before_names, unreg_before_names, stop_before_names)
        ):
            if idx % 2:
                app_config = AppConfig.ScriptStyle
            else:
                app_config = AppConfig.RemoteThreadApp

            if target in start_before_names:
                self.build_create_suite(
                    f1_create_items=[
                        F1CreateItem(
                            name=target,
                            auto_start=True,
                            target_rtn=outer_f1,
                            app_config=app_config,
                        )
                    ],
                    validate_config=False,
                )
                confirm_req, confirm_serial = target_builds[req_type](
                    cmd_runners=target, targets=requestors, exp_targets=requestors
                )
                target_confirms_before.append(
                    ConfirmResponse(
                        cmd_runners=[self.commander_name],
                        confirm_cmd=confirm_req,
                        confirm_serial_num=confirm_serial,
                        confirmers=target,
                    )
                )
            elif target in unreg_before_names:
                self.build_create_suite(
                    f1_create_items=[
                        F1CreateItem(
                            name=target,
                            auto_start=False,
                            target_rtn=outer_f1,
                            app_config=app_config,
                        )
                    ],
                    validate_config=False,
                )
                self.build_unreg_suite(names=target)
            elif target in stop_before_names:
                self.build_create_suite(
                    f1_create_items=[
                        F1CreateItem(
                            name=target,
                            auto_start=True,
                            target_rtn=outer_f1,
                            app_config=app_config,
                        )
                    ],
                    validate_config=False,
                )
                # stop now, join later
                self.build_exit_suite(
                    cmd_runner=self.commander_name, names=target, validate_config=False
                )
            else:
                raise IncorrectDataDetected(
                    "build_srrw_scenario "
                    f"{target=} not found in "
                    f"{start_before_names=} nor "
                    f"{unreg_before_names=} nor "
                    f"{stop_before_names=}"
                )

        ################################################################
        # for recv/wait, make sure running before send/resume
        ################################################################
        if req_type in (st.ReqType.Smart_send, st.ReqType.Smart_resume):
            if start_before_names:
                self.add_cmd(
                    WaitForRequestTimeouts(
                        cmd_runners=self.commander_name,
                        actor_names=start_before_names,
                        timeout_names=requestors,
                    )
                )
        else:
            for confirm in target_confirms_before:
                self.add_cmd(confirm)

        ################################################################
        # issue request
        ################################################################
        if stop_before_names:
            stopped_remotes = stop_before_names
            exp_targets = start_before_names
        else:
            stopped_remotes = unreg_after_names | stop_after_err_names
            exp_targets = start_before_names | unreg_before_names | stop_after_ok_names

        confirm_req_0, confirm_serial_0 = request_builds[req_type](
            cmd_runners=requestors,
            targets=all_targets,
            exp_targets=exp_targets,
            stopped_targets=stopped_remotes,
        )

        ################################################################
        # confirm response now if we should have raised error for
        # stopped remotes
        ################################################################
        if stop_before_names:
            self.add_cmd(
                ConfirmResponse(
                    cmd_runners=[self.commander_name],
                    confirm_cmd=confirm_req_0,
                    confirm_serial_num=confirm_serial_0,
                    confirmers=requestors,
                )
            )
            ############################################################
            # we need this request for the after targets when the first
            # request ends early because of stopped remotes
            ############################################################
            if after_targets:
                stopped_remotes = unreg_after_names | stop_after_err_names
                exp_targets = unreg_before_names | stop_after_ok_names

                confirm_req_1, confirm_serial_1 = request_builds[req_type](
                    cmd_runners=requestors,
                    targets=after_targets,
                    exp_targets=exp_targets,
                    stopped_targets=stopped_remotes,
                )

        ################################################################
        # Create and start unreg_before and stop_after_ok and issue the
        # target_rtn request. Note unreg_before is used both before and
        # after the request
        ################################################################
        for idx, target in enumerate(
            roundrobin(unreg_before_names, stop_after_ok_names)
        ):
            if idx % 2:
                app_config = AppConfig.ScriptStyle
            else:
                app_config = AppConfig.RemoteThreadApp

            self.build_create_suite(
                f1_create_items=[
                    F1CreateItem(
                        name=target,
                        auto_start=True,
                        target_rtn=outer_f1,
                        app_config=app_config,
                    )
                ],
                validate_config=False,
            )

            confirm_req, confirm_serial = target_builds[req_type](
                cmd_runners=target, targets=requestors, exp_targets=requestors
            )
            target_confirms_after.append(
                ConfirmResponse(
                    cmd_runners=[self.commander_name],
                    confirm_cmd=confirm_req,
                    confirm_serial_num=confirm_serial,
                    confirmers=target,
                )
            )

        ################################################################
        # build unreg_after and stop_after_err
        ################################################################
        for idx, target in enumerate(
            roundrobin(unreg_after_names, stop_after_err_names)
        ):
            if idx % 2:
                app_config = AppConfig.ScriptStyle
            else:
                app_config = AppConfig.RemoteThreadApp

            if target in unreg_after_names:
                self.build_create_suite(
                    f1_create_items=[
                        F1CreateItem(
                            name=target,
                            auto_start=False,
                            target_rtn=outer_f1,
                            app_config=app_config,
                        )
                    ],
                    validate_config=False,
                )
                self.build_unreg_suite(names=target)
            elif target in stop_after_err_names:
                self.build_create_suite(
                    f1_create_items=[
                        F1CreateItem(
                            name=target,
                            auto_start=True,
                            target_rtn=outer_f1,
                            app_config=app_config,
                        )
                    ],
                    validate_config=False,
                )
                self.build_exit_suite(
                    cmd_runner=self.commander_name, names=target, validate_config=False
                )
                self.build_join_suite(
                    cmd_runners=self.commander_name,
                    join_target_names=target,
                    validate_config=False,
                )
            else:
                raise IncorrectDataDetected(
                    "build_srrw_scenario "
                    f"{target=} not found in "
                    f"{unreg_after_names=} nor "
                    f"{stop_after_err_names=}"
                )

        ####################################################
        # confirm the resumes
        ####################################################
        if not stop_before_names:
            self.add_cmd(
                ConfirmResponse(
                    cmd_runners=[self.commander_name],
                    confirm_cmd=confirm_req_0,
                    confirm_serial_num=confirm_serial_0,
                    confirmers=requestors,
                )
            )
        elif after_targets:
            self.add_cmd(
                ConfirmResponse(
                    cmd_runners=[self.commander_name],
                    confirm_cmd=confirm_req_1,
                    confirm_serial_num=confirm_serial_1,
                    confirmers=requestors,
                )
            )

        for confirm in target_confirms_after:
            self.add_cmd(confirm)

    ####################################################################
    # build_wait_scenario
    ####################################################################
    def build_wait_scenario(
        self,
        num_waiters: int,
        num_start_before: int,
        num_unreg_before: int,
        num_stop_before: int,
        num_unreg_after: int,
        num_stop_after_ok: int,
        num_stop_after_err: int,
    ) -> None:
        """Test meta configuration scenarios.

        Args:
            num_waiters: number of threads doing resumes
            num_start_before: number of target_rtn threads that will
                be started and issue a wait before the resume is done,
                and should succeed
            num_unreg_before: number of target_rtn threads that will be
                registered and then unregistered before the resume, and
                then started after the resume, and should succeed
            num_stop_before: number of target_rtn threads that will
                be started and then stopped (but not joined) before the
                resume, and should result in a not alive error
            num_unreg_after: number of target_rtn threads that will be
                unregistered after the resume, and should cause an error
            num_stop_after_ok: number of target_rtn threads that will
                be started after the resume is issued, and will stay
                alive long enough for the resume to set the wait_flag,
                and will then be stopped and joined, and should result
                in success
            num_stop_after_err: number of target_rtn threads that will
                be started after the resume is issued, and will quickly
                be stopped and joined before the resume has a chance to
                see that is is alive to sety the wait_flag, and should
                result in a not alive error

        """
        # Make sure we have enough threads
        total_arg_counts = (
            num_waiters
            + num_start_before
            + num_unreg_before
            + num_stop_before
            + num_unreg_after
            + num_stop_after_ok
            + num_stop_after_err
        )
        assert total_arg_counts <= len(self.unregistered_names)

        assert num_waiters > 0

        num_active_needed = num_waiters + 1  # plus 1 for commander

        self.build_config(
            cmd_runner=self.commander_name,
            num_active=num_active_needed,
        )

        # remove commander
        active_names_copy = self.active_names - {self.commander_name}

        ################################################################
        # choose waiter_names
        ################################################################
        waiter_names = self.choose_names(
            name_collection=active_names_copy,
            num_names_needed=num_waiters,
            update_collection=True,
            var_name_for_log="waiter_names",
        )

        ################################################################
        # choose start_before_names
        ################################################################
        unregistered_names_copy = self.unregistered_names.copy()
        start_before_names = self.choose_names(
            name_collection=unregistered_names_copy,
            num_names_needed=num_start_before,
            update_collection=True,
            var_name_for_log="start_before_names",
        )

        ################################################################
        # choose unreg_before_names
        ################################################################
        unreg_before_names = self.choose_names(
            name_collection=unregistered_names_copy,
            num_names_needed=num_unreg_before,
            update_collection=True,
            var_name_for_log="unreg_before_names",
        )

        ################################################################
        # choose stop_before_names
        ################################################################
        stop_before_names = self.choose_names(
            name_collection=unregistered_names_copy,
            num_names_needed=num_stop_before,
            update_collection=True,
            var_name_for_log="stop_before_names",
        )

        ################################################################
        # choose unreg_after_names
        ################################################################
        unreg_after_names = self.choose_names(
            name_collection=unregistered_names_copy,
            num_names_needed=num_unreg_after,
            update_collection=True,
            var_name_for_log="unreg_after_names",
        )

        ################################################################
        # choose stop_after_ok_names
        ################################################################
        stop_after_ok_names = self.choose_names(
            name_collection=unregistered_names_copy,
            num_names_needed=num_stop_after_ok,
            update_collection=True,
            var_name_for_log="stop_after_ok_names",
        )

        ################################################################
        # choose stop_after_ok_names
        ################################################################
        stop_after_err_names = self.choose_names(
            name_collection=unregistered_names_copy,
            num_names_needed=num_stop_after_err,
            update_collection=True,
            var_name_for_log="stop_after_err_names",
        )

        all_targets: list[str] = (
            start_before_names
            + unreg_before_names
            + stop_before_names
            + unreg_after_names
            + stop_after_ok_names
            + stop_after_err_names
        )

        after_targets: list[str] = (
            unreg_before_names
            + unreg_after_names
            + stop_after_ok_names
            + stop_after_err_names
        )

        ################################################################
        # monkeypatch for SmartThread._get_target_state
        ################################################################
        a_target_mock_dict = {}
        if stop_after_err_names:
            for waiter_name in waiter_names:
                a_sub_dict = {}
                for stop_name in stop_after_err_names:
                    a_sub_dict[stop_name] = (
                        st.ThreadState.Alive,
                        st.ThreadState.Registered,
                    )
                a_target_mock_dict[waiter_name] = a_sub_dict

        MockGetTargetState(targets=a_target_mock_dict, config_ver=self)

        wait_serial_num_2 = 0

        resume_confirms_before: list[ConfirmResponse] = []
        resume_confirms_after: list[ConfirmResponse] = []

        for idx, resumer in enumerate(
            roundrobin(start_before_names, unreg_before_names, stop_before_names)
        ):
            if idx % 2:
                app_config = AppConfig.ScriptStyle
            else:
                app_config = AppConfig.RemoteThreadApp

            if resumer in start_before_names:
                self.build_create_suite(
                    f1_create_items=[
                        F1CreateItem(
                            name=resumer,
                            auto_start=True,
                            target_rtn=outer_f1,
                            app_config=app_config,
                        )
                    ],
                    validate_config=False,
                )
                resume_serial_num = self.add_cmd(
                    Resume(
                        cmd_runners=resumer,
                        targets=waiter_names,
                        exp_resumed_targets=waiter_names,
                        stopped_remotes=set(),
                    )
                )
                resume_confirms_before.append(
                    ConfirmResponse(
                        cmd_runners=[self.commander_name],
                        confirm_cmd="Resume",
                        confirm_serial_num=resume_serial_num,
                        confirmers=resumer,
                    )
                )
            elif resumer in unreg_before_names:
                self.build_create_suite(
                    f1_create_items=[
                        F1CreateItem(
                            name=resumer,
                            auto_start=False,
                            target_rtn=outer_f1,
                            app_config=app_config,
                        )
                    ],
                    validate_config=False,
                )
                self.build_unreg_suite(names=resumer, validate_config=False)
            elif resumer in stop_before_names:
                self.build_create_suite(
                    f1_create_items=[
                        F1CreateItem(
                            name=resumer,
                            auto_start=True,
                            target_rtn=outer_f1,
                            app_config=app_config,
                        )
                    ],
                    validate_config=False,
                )
                # stop now, join later
                self.build_exit_suite(
                    cmd_runner=self.commander_name, names=resumer, validate_config=False
                )
            else:
                raise IncorrectDataDetected(
                    "build_wait_scenario "
                    f"{resumer=} not found in "
                    f"{start_before_names=} nor "
                    f"{unreg_before_names=} nor "
                    f"{stop_before_names=}"
                )

        ################################################################
        # confirm the before resumes
        ################################################################
        for confirm in resume_confirms_before:
            self.add_cmd(confirm)
        ################################################################
        # issue smart_wait
        ################################################################
        if stop_before_names:
            stopped_remotes = stop_before_names
            exp_resumers = set(start_before_names)
        else:
            stopped_remotes = unreg_after_names + stop_after_err_names
            exp_resumers = (
                set(start_before_names)
                | set(unreg_before_names)
                | set(stop_after_ok_names)
            )

        wait_serial_num_1 = self.add_cmd(
            Wait(
                cmd_runners=waiter_names,
                resumers=all_targets,
                exp_resumers=exp_resumers,
                stopped_remotes=stopped_remotes,
            )
        )

        ################################################################
        # confirm response now if we should have raised error for
        # stopped remotes
        ################################################################
        if stop_before_names:
            self.add_cmd(
                ConfirmResponse(
                    cmd_runners=[self.commander_name],
                    confirm_cmd="Wait",
                    confirm_serial_num=wait_serial_num_1,
                    confirmers=waiter_names,
                )
            )
            ############################################################
            # we need this wait for the after wait resumes when the
            # first wait ends early because of stopped remotes
            ############################################################
            if after_targets:
                stopped_remotes = unreg_after_names + stop_after_err_names
                exp_resumers = set(unreg_before_names) | set(stop_after_ok_names)
                wait_serial_num_2 = self.add_cmd(
                    Wait(
                        cmd_runners=waiter_names,
                        resumers=after_targets,
                        exp_resumers=exp_resumers,
                        stopped_remotes=stopped_remotes,
                    )
                )

        ################################################################
        # Create and start unreg_before and stop_after_ok and issue the
        # resume. Note unreg_before is used both before and after the
        # wait
        ################################################################
        for idx, resumer in enumerate(
            roundrobin(unreg_before_names, stop_after_ok_names)
        ):
            if idx % 2:
                app_config = AppConfig.ScriptStyle
            else:
                app_config = AppConfig.RemoteThreadApp

            self.build_create_suite(
                f1_create_items=[
                    F1CreateItem(
                        name=resumer,
                        auto_start=True,
                        target_rtn=outer_f1,
                        app_config=app_config,
                    )
                ],
                validate_config=False,
            )
            resume_serial_num = self.add_cmd(
                Resume(
                    cmd_runners=resumer,
                    targets=waiter_names,
                    exp_resumed_targets=waiter_names,
                    stopped_remotes=set(),
                )
            )
            resume_confirms_after.append(
                ConfirmResponse(
                    cmd_runners=[self.commander_name],
                    confirm_cmd="Resume",
                    confirm_serial_num=resume_serial_num,
                    confirmers=resumer,
                )
            )

        ################################################################
        # build unreg_after and stop_after_err
        ################################################################
        for idx, resumer in enumerate(
            roundrobin(unreg_after_names, stop_after_err_names)
        ):
            if idx % 2:
                app_config = AppConfig.ScriptStyle
            else:
                app_config = AppConfig.RemoteThreadApp

            if resumer in unreg_after_names:
                self.build_create_suite(
                    f1_create_items=[
                        F1CreateItem(
                            name=resumer,
                            auto_start=False,
                            target_rtn=outer_f1,
                            app_config=app_config,
                        )
                    ],
                    validate_config=False,
                )
                self.build_unreg_suite(names=resumer, validate_config=False)
            elif resumer in stop_after_err_names:
                self.build_create_suite(
                    f1_create_items=[
                        F1CreateItem(
                            name=resumer,
                            auto_start=True,
                            target_rtn=outer_f1,
                            app_config=app_config,
                        )
                    ],
                    validate_config=False,
                )
                self.build_exit_suite(
                    cmd_runner=self.commander_name, names=resumer, validate_config=False
                )
                self.build_join_suite(
                    cmd_runners=self.commander_name,
                    join_target_names=resumer,
                    validate_config=False,
                )
            else:
                raise IncorrectDataDetected(
                    "build_wait_scenario "
                    f"{resumer=} not found in "
                    f"{unreg_after_names=} nor "
                    f"{stop_after_err_names=}"
                )

        ####################################################
        # confirm the waits
        ####################################################
        if not stop_before_names:
            self.add_cmd(
                ConfirmResponse(
                    cmd_runners=[self.commander_name],
                    confirm_cmd="Wait",
                    confirm_serial_num=wait_serial_num_1,
                    confirmers=waiter_names,
                )
            )
        elif after_targets:
            self.add_cmd(
                ConfirmResponse(
                    cmd_runners=[self.commander_name],
                    confirm_cmd="Wait",
                    confirm_serial_num=wait_serial_num_2,
                    confirmers=waiter_names,
                )
            )

        for confirm in resume_confirms_after:
            self.add_cmd(confirm)

    ####################################################################
    # build_resume_timeout_suite
    ####################################################################
    def build_resume_timeout_suite(
        self,
        timeout_type: TimeoutType,
        num_resumers: int,
        num_active: int,
        num_registered_before: int,
        num_registered_after: int,
        num_unreg_no_delay: int,
        num_unreg_delay: int,
        num_stopped: int,
    ) -> None:
        """Add ConfigCmd items for smart_resume timeout scenarios.

        Args:
            timeout_type: specifies whether to issue the send_cmd with
                timeout, and if so whether the send_cmd should timeout
                or, by starting exited threads in time, not timeout
            num_resumers: number of threads doing resumes
            num_active: number threads active that will wait before the
                resume is done. This is the most expected use case. No
                resume timeout should occur for active targets.
            num_registered_before: number threads registered that will
                be started and then wait before the resume is issued.
                This case provides a variation by having a configuration
                change occur while the active targets are waiting. No
                resume timeout should occur for registered_before
                targets.
            num_registered_after: number threads registered that are
                started and wait after the resume is issued. This case
                provides a variation of a resume target_rtn being not
                alive when the resume is issued, and then a
                configuration change while the resume is running and the
                resume sees that the target_rtn is now alive. There is
                no significant delay between the resume and the start to
                expect the registered_after targets to cause a timeout.
            num_unreg_no_delay: number threads unregistered before the
                resume is done, and are then created and started within
                the allowed timeout
            num_unreg_delay: number threads unregistered before the
                resume is done, and are then created and started after
                the allowed timeout
            num_stopped: number of threads stopped before the
                resume and are resurrected after the resume. This should
                cause the resume to fail with a NotAlive error, and the
                stopped threads will wait and will need a new resume.

        """
        # Make sure we have enough threads
        assert (
            num_resumers
            + num_active
            + num_registered_before
            + num_registered_after
            + num_unreg_no_delay
            + num_unreg_delay
            + num_stopped
        ) <= len(self.unregistered_names)

        assert num_resumers > 0

        timeout_time = (
            (num_active * 0.16)
            + (num_registered_before * 0.16)
            + (num_registered_after * 0.16)
            + (num_unreg_no_delay * 0.32)
            + (num_unreg_delay * 0.16)
            + (num_stopped * 0.32)
        )

        pause_time = 0.5
        if timeout_type == TimeoutType.TimeoutFalse:
            timeout_time *= 4  # prevent timeout
            pause_time = timeout_time * 0.10
        elif timeout_type == TimeoutType.TimeoutTrue:
            # timeout_time *= 0.5  # force timeout
            pause_time = timeout_time * 2

        resumers = get_names("resumer_", num_resumers)

        active_waiters = get_names("active_waiter_", num_active)

        reg_waiters = get_names("reg_waiter_", num_registered_before)

        reg_delay_waiters = get_names("reg_delay_waiter_", num_registered_after)

        unreg_waiters = get_names("unreg_waiter_", num_unreg_no_delay)

        unreg_delay_waiters = get_names("unreg_delay_waiter_", num_unreg_delay)

        stopped_waiters = get_names("stopped_waiter_", num_stopped)

        self.create_config(
            unreg_names=unreg_waiters | unreg_delay_waiters,
            reg_names=reg_waiters | reg_delay_waiters,
            active_names=resumers | active_waiters,
            stopped_names=stopped_waiters,
        )

        all_targets: set[str] = (
            active_waiters
            | reg_waiters
            | reg_delay_waiters
            | unreg_waiters
            | unreg_delay_waiters
            | stopped_waiters
        )

        timeout_names = unreg_delay_waiters | reg_delay_waiters

        if stopped_waiters:
            exp_resumed_targets = active_waiters | reg_waiters
        else:
            if timeout_type != TimeoutType.TimeoutTrue:
                exp_resumed_targets = all_targets
            else:
                exp_resumed_targets = active_waiters | reg_waiters | unreg_waiters

        ################################################################
        # issue smart_wait for active_waiters
        ################################################################
        if active_waiters:
            wait_active_target_serial_num = self.add_cmd(
                Wait(
                    cmd_runners=active_waiters, resumers=resumers, exp_resumers=resumers
                )
            )

        ################################################################
        # start reg_waiters issue smart_wait
        # This provides a variation where a configuration change (start)
        # is done while the above wait for active targets is in progress
        ################################################################
        if reg_waiters:
            self.build_start_suite(start_names=reg_waiters)
            wait_reg_before_target_serial_num = self.add_cmd(
                Wait(cmd_runners=reg_waiters, resumers=resumers, exp_resumers=resumers)
            )

        ################################################################
        # issue smart_resume
        ################################################################
        if timeout_type == TimeoutType.TimeoutNone:
            resume_to_confirm = "Resume"
            resume_serial_num = self.add_cmd(
                Resume(
                    cmd_runners=resumers,
                    targets=all_targets,
                    exp_resumed_targets=exp_resumed_targets,
                    stopped_remotes=stopped_waiters,
                )
            )
        elif timeout_type == TimeoutType.TimeoutFalse:
            resume_to_confirm = "ResumeTimeoutFalse"
            resume_serial_num = self.add_cmd(
                ResumeTimeoutFalse(
                    cmd_runners=resumers,
                    targets=all_targets,
                    exp_resumed_targets=exp_resumed_targets,
                    stopped_remotes=stopped_waiters,
                    timeout=timeout_time,
                )
            )
        else:
            resume_to_confirm = "ResumeTimeoutTrue"
            resume_serial_num = self.add_cmd(
                ResumeTimeoutTrue(
                    cmd_runners=resumers,
                    targets=all_targets,
                    exp_resumed_targets=exp_resumed_targets,
                    stopped_remotes=stopped_waiters,
                    timeout=timeout_time,
                    timeout_names=timeout_names,
                )
            )

        ################################################################
        # prevent stopped_waiters from getting started too soon
        ################################################################
        if stopped_waiters:
            self.add_cmd(
                ConfirmResponse(
                    cmd_runners=[self.commander_name],
                    confirm_cmd=resume_to_confirm,
                    confirm_serial_num=resume_serial_num,
                    confirmers=resumers,
                )
            )
        ################################################################
        # create and start unreg_waiters and build smart_wait
        ################################################################
        if unreg_waiters:
            f1_create_items: list[F1CreateItem] = []
            for idx, name in enumerate(unreg_waiters):
                if idx % 2:
                    app_config = AppConfig.ScriptStyle
                else:
                    app_config = AppConfig.RemoteThreadApp

                f1_create_items.append(
                    F1CreateItem(
                        name=name,
                        auto_start=True,
                        target_rtn=outer_f1,
                        app_config=app_config,
                    )
                )
            self.build_create_suite(
                f1_create_items=f1_create_items, validate_config=False
            )

            wait_unreg_no_delay_serial_num = self.add_cmd(
                Wait(
                    cmd_runners=unreg_waiters, resumers=resumers, exp_resumers=resumers
                )
            )

        ################################################################
        # build stopped_waiters smart_wait
        ################################################################
        if stopped_waiters:
            self.build_join_suite(
                cmd_runners=self.commander_name, join_target_names=stopped_waiters
            )

            for stopped_no_delay_name in stopped_waiters:
                self.add_cmd(
                    VerifyConfig(
                        cmd_runners=self.commander_name,
                        verify_type=VerifyType.VerifyNotPaired,
                        names_to_check=stopped_no_delay_name,
                    )
                )

            f1_create_items = []
            for idx, name in enumerate(stopped_waiters):
                if idx % 2:
                    app_config = AppConfig.ScriptStyle
                else:
                    app_config = AppConfig.RemoteThreadApp

                f1_create_items.append(
                    F1CreateItem(
                        name=name,
                        auto_start=True,
                        target_rtn=outer_f1,
                        app_config=app_config,
                    )
                )
            self.build_create_suite(
                f1_create_items=f1_create_items, validate_config=False
            )

            wait_stopped_no_delay_serial_num = self.add_cmd(
                Wait(
                    cmd_runners=stopped_waiters,
                    resumers=resumers,
                    exp_resumers=resumers,
                )
            )

        ################################################################
        # wait for resume timeouts to be known
        ################################################################
        self.add_cmd(Pause(cmd_runners=self.commander_name, pause_seconds=pause_time))

        ################################################################
        # start reg_delay_waiters and issue smart_wait
        ################################################################
        if reg_delay_waiters:
            self.build_start_suite(start_names=reg_delay_waiters)
            wait_reg_after_target_serial_num = self.add_cmd(
                Wait(
                    cmd_runners=reg_delay_waiters,
                    resumers=resumers,
                    exp_resumers=resumers,
                )
            )

        ################################################################
        # build unreg_delay_waiters smart_wait
        ################################################################
        if unreg_delay_waiters:
            f1_create_items = []
            for idx, name in enumerate(unreg_delay_waiters):
                if idx % 2:
                    app_config = AppConfig.ScriptStyle
                else:
                    app_config = AppConfig.RemoteThreadApp

                f1_create_items.append(
                    F1CreateItem(
                        name=name,
                        auto_start=True,
                        target_rtn=outer_f1,
                        app_config=app_config,
                    )
                )
            self.build_create_suite(
                f1_create_items=f1_create_items, validate_config=False
            )

            wait_unreg_delay_serial_num = self.add_cmd(
                Wait(
                    cmd_runners=unreg_delay_waiters,
                    resumers=resumers,
                    exp_resumers=resumers,
                )
            )

        ####################################################
        # confirm the active target_rtn waits
        ####################################################
        if active_waiters:
            self.add_cmd(
                ConfirmResponse(
                    cmd_runners=[self.commander_name],
                    confirm_cmd="Wait",
                    confirm_serial_num=wait_active_target_serial_num,
                    confirmers=active_waiters,
                )
            )

        ####################################################
        # confirm the registered target_rtn waits
        ####################################################
        if reg_waiters:
            self.add_cmd(
                ConfirmResponse(
                    cmd_runners=[self.commander_name],
                    confirm_cmd="Wait",
                    confirm_serial_num=wait_reg_before_target_serial_num,
                    confirmers=reg_waiters,
                )
            )

        ####################################################
        # confirm the registered target_rtn waits
        ####################################################
        if reg_delay_waiters:
            if timeout_type == TimeoutType.TimeoutTrue or stopped_waiters:
                self.add_cmd(
                    ConfirmResponseNot(
                        cmd_runners=[self.commander_name],
                        confirm_cmd="Wait",
                        confirm_serial_num=wait_reg_after_target_serial_num,
                        confirmers=reg_delay_waiters,
                    )
                )

                resume_serial_num2 = self.add_cmd(
                    ResumeTimeoutFalse(
                        cmd_runners=resumers,
                        targets=reg_delay_waiters,
                        exp_resumed_targets=reg_delay_waiters,
                        timeout=0.5,
                    )
                )
                self.add_cmd(
                    ConfirmResponse(
                        cmd_runners=[self.commander_name],
                        confirm_cmd="ResumeTimeoutFalse",
                        confirm_serial_num=resume_serial_num2,
                        confirmers=resumers,
                    )
                )
            self.add_cmd(
                ConfirmResponse(
                    cmd_runners=[self.commander_name],
                    confirm_cmd="Wait",
                    confirm_serial_num=wait_reg_after_target_serial_num,
                    confirmers=reg_delay_waiters,
                )
            )

        ####################################################
        # confirm the unreg_waiters
        ####################################################
        if unreg_waiters:
            # if error_stopped_target and stopped_waiters:
            if stopped_waiters:
                self.add_cmd(
                    ConfirmResponseNot(
                        cmd_runners=[self.commander_name],
                        confirm_cmd="Wait",
                        confirm_serial_num=wait_unreg_no_delay_serial_num,
                        confirmers=unreg_waiters,
                    )
                )

                resume_serial_num2 = self.add_cmd(
                    ResumeTimeoutFalse(
                        cmd_runners=resumers,
                        targets=unreg_waiters,
                        exp_resumed_targets=unreg_waiters,
                        timeout=0.5,
                    )
                )
                self.add_cmd(
                    ConfirmResponse(
                        cmd_runners=[self.commander_name],
                        confirm_cmd="ResumeTimeoutFalse",
                        confirm_serial_num=resume_serial_num2,
                        confirmers=resumers,
                    )
                )
            self.add_cmd(
                ConfirmResponse(
                    cmd_runners=[self.commander_name],
                    confirm_cmd="Wait",
                    confirm_serial_num=wait_unreg_no_delay_serial_num,
                    confirmers=unreg_waiters,
                )
            )
        ####################################################
        # confirm the unreg_delay_waiters
        ####################################################
        if unreg_delay_waiters:
            if timeout_type == TimeoutType.TimeoutTrue or stopped_waiters:
                self.add_cmd(
                    ConfirmResponseNot(
                        cmd_runners=[self.commander_name],
                        confirm_cmd="Wait",
                        confirm_serial_num=wait_unreg_delay_serial_num,
                        confirmers=unreg_delay_waiters,
                    )
                )

                resume_serial_num2 = self.add_cmd(
                    ResumeTimeoutFalse(
                        cmd_runners=resumers,
                        targets=unreg_delay_waiters,
                        exp_resumed_targets=unreg_delay_waiters,
                        timeout=0.5,
                    )
                )
                self.add_cmd(
                    ConfirmResponse(
                        cmd_runners=[self.commander_name],
                        confirm_cmd="ResumeTimeoutFalse",
                        confirm_serial_num=resume_serial_num2,
                        confirmers=resumers,
                    )
                )
            self.add_cmd(
                ConfirmResponse(
                    cmd_runners=[self.commander_name],
                    confirm_cmd="Wait",
                    confirm_serial_num=wait_unreg_delay_serial_num,
                    confirmers=unreg_delay_waiters,
                )
            )
        ####################################################
        # confirm the stopped_waiters
        ####################################################
        if stopped_waiters:
            # if error_stopped_target and stopped_waiters:
            if stopped_waiters:
                self.add_cmd(
                    ConfirmResponseNot(
                        cmd_runners=[self.commander_name],
                        confirm_cmd="Wait",
                        confirm_serial_num=wait_stopped_no_delay_serial_num,
                        confirmers=stopped_waiters,
                    )
                )

                resume_serial_num2 = self.add_cmd(
                    ResumeTimeoutFalse(
                        cmd_runners=resumers,
                        targets=stopped_waiters,
                        exp_resumed_targets=stopped_waiters,
                        timeout=0.5,
                    )
                )
                self.add_cmd(
                    ConfirmResponse(
                        cmd_runners=[self.commander_name],
                        confirm_cmd="ResumeTimeoutFalse",
                        confirm_serial_num=resume_serial_num2,
                        confirmers=resumers,
                    )
                )
            self.add_cmd(
                ConfirmResponse(
                    cmd_runners=[self.commander_name],
                    confirm_cmd="Wait",
                    confirm_serial_num=wait_stopped_no_delay_serial_num,
                    confirmers=stopped_waiters,
                )
            )

        ####################################################
        # confirm the resumers
        ####################################################
        if not stopped_waiters:
            self.add_cmd(
                ConfirmResponse(
                    cmd_runners=[self.commander_name],
                    confirm_cmd=resume_to_confirm,
                    confirm_serial_num=resume_serial_num,
                    confirmers=resumers,
                )
            )

    ####################################################################
    # build_rotate_state_scenario
    ####################################################################
    def build_rotate_state_scenario(
        self,
        timeout_type: TimeoutType,
        req0: st.ReqType,
        req1: st.ReqType,
        req0_when_req1_state: tuple[st.ThreadState, int],
        req0_when_req1_lap: int,
        req1_lap: int,
    ) -> None:
        """Add cmds to run scenario.

        Args:
            timeout_type: specifies whether the SmartRequest should
                be coded with timeout, and whether it be False or True
            req0: the SmartRequest that req0 will make
            req1: the SmartRequest that req1 will make
            req0_when_req1_state: req0 will issue SmartRequest when
                req1 transitions to this state
            req0_when_req1_lap: req0 will issue SmartRequest when
                req1 transitions during this lap
            req1_lap: lap 0 or 1 when req1 SmartRequest is to be
                issued

        """
        # Make sure we have enough threads. Each of the scenarios will
        # require one thread for the commander, one thread for req0,
        # and one thread for req1, for a total of three.
        assert 3 <= len(self.unregistered_names)

        self.auto_calling_refresh_msg = False
        self.build_config(
            cmd_runner=self.commander_name, num_active=2
        )  # one for commander and one for req0

        active_names_copy = self.active_names - {self.commander_name}

        ################################################################
        # choose receiver_names
        ################################################################
        req0_names = self.choose_names(
            name_collection=active_names_copy,
            num_names_needed=1,
            update_collection=True,
            var_name_for_log="req0_names",
        )

        ################################################################
        # choose receiver_names
        ################################################################
        req1_names = self.choose_names(
            name_collection=self.unregistered_names,
            num_names_needed=1,
            update_collection=False,
            var_name_for_log="req1_names",
        )

        ################################################################
        # setup the messages to send
        ################################################################
        req0_name = req0_names[0]
        req1_name = req1_names[0]

        sender_msgs = SendRecvMsgs(
            sender_names=[req0_name, req1_name],
            receiver_names=[req0_name, req1_name],
            num_msgs=1,
            text="build_rotate_state_scenario",
        )

        req0_deadlock_remotes: set[str] = set()

        req1_deadlock_remotes: set[str] = set()

        req0_specific_args: dict[str, Any] = {
            "sender_msgs": sender_msgs,
            "deadlock_remotes": req0_deadlock_remotes,
            "sync_set_ack_remotes": set(),
            "exp_senders": set(),
            "exp_receivers": set(),
            "exp_resumed_targets": set(),
            "exp_resumers": set(),
            "exp_syncers": set(),
        }

        req1_specific_args: dict[str, Any] = {
            "sender_msgs": sender_msgs,
            "deadlock_remotes": req1_deadlock_remotes,
            "sync_set_ack_remotes": req0_name,
            "exp_senders": set(),
            "exp_receivers": set(),
            "exp_resumed_targets": set(),
            "exp_resumers": set(),
            "exp_syncers": set(),
        }

        ################################################################
        # request rtns
        ################################################################
        request_build_rtns: dict[st.ReqType, Callable[..., RequestConfirmParms]] = {
            st.ReqType.Smart_send: self.build_send_msg_request,
            st.ReqType.Smart_recv: self.build_recv_msg_request,
            st.ReqType.Smart_resume: self.build_resume_request,
            st.ReqType.Smart_sync: self.build_sync_request,
            st.ReqType.Smart_wait: self.build_wait_request,
        }

        req0_stopped_remotes: set[str] = set()
        req1_stopped_remotes: set[str] = set()
        req1_timeout_type: TimeoutType = TimeoutType.TimeoutNone
        supress_req1 = False

        reset_ops_count = False

        class ReqCategory(Enum):
            Throw = auto()
            Catch = auto()
            Handshake = auto()

        @dataclass
        class ReqFlags:
            req0_category: ReqCategory
            req1_category: ReqCategory
            req_matched: bool
            req_deadlock: bool

        request_table: dict[tuple[st.ReqType, st.ReqType], ReqFlags] = {
            (st.ReqType.Smart_send, st.ReqType.Smart_send): ReqFlags(
                req0_category=ReqCategory.Throw,
                req1_category=ReqCategory.Throw,
                req_matched=False,
                req_deadlock=False,
            ),
            (st.ReqType.Smart_send, st.ReqType.Smart_recv): ReqFlags(
                req0_category=ReqCategory.Throw,
                req1_category=ReqCategory.Catch,
                req_matched=True,
                req_deadlock=False,
            ),
            (st.ReqType.Smart_send, st.ReqType.Smart_resume): ReqFlags(
                req0_category=ReqCategory.Throw,
                req1_category=ReqCategory.Throw,
                req_matched=False,
                req_deadlock=False,
            ),
            (st.ReqType.Smart_send, st.ReqType.Smart_sync): ReqFlags(
                req0_category=ReqCategory.Throw,
                req1_category=ReqCategory.Handshake,
                req_matched=False,
                req_deadlock=False,
            ),
            (st.ReqType.Smart_send, st.ReqType.Smart_wait): ReqFlags(
                req0_category=ReqCategory.Throw,
                req1_category=ReqCategory.Catch,
                req_matched=False,
                req_deadlock=False,
            ),
            (st.ReqType.Smart_recv, st.ReqType.Smart_recv): ReqFlags(
                req0_category=ReqCategory.Catch,
                req1_category=ReqCategory.Catch,
                req_matched=False,
                req_deadlock=True,
            ),
            (st.ReqType.Smart_recv, st.ReqType.Smart_send): ReqFlags(
                req0_category=ReqCategory.Catch,
                req1_category=ReqCategory.Throw,
                req_matched=True,
                req_deadlock=False,
            ),
            (st.ReqType.Smart_recv, st.ReqType.Smart_resume): ReqFlags(
                req0_category=ReqCategory.Catch,
                req1_category=ReqCategory.Throw,
                req_matched=False,
                req_deadlock=False,
            ),
            (st.ReqType.Smart_recv, st.ReqType.Smart_sync): ReqFlags(
                req0_category=ReqCategory.Catch,
                req1_category=ReqCategory.Handshake,
                req_matched=False,
                req_deadlock=True,
            ),
            (st.ReqType.Smart_recv, st.ReqType.Smart_wait): ReqFlags(
                req0_category=ReqCategory.Catch,
                req1_category=ReqCategory.Catch,
                req_matched=False,
                req_deadlock=True,
            ),
            (st.ReqType.Smart_resume, st.ReqType.Smart_send): ReqFlags(
                req0_category=ReqCategory.Throw,
                req1_category=ReqCategory.Throw,
                req_matched=False,
                req_deadlock=False,
            ),
            (st.ReqType.Smart_resume, st.ReqType.Smart_recv): ReqFlags(
                req0_category=ReqCategory.Throw,
                req1_category=ReqCategory.Catch,
                req_matched=False,
                req_deadlock=False,
            ),
            (st.ReqType.Smart_resume, st.ReqType.Smart_resume): ReqFlags(
                req0_category=ReqCategory.Throw,
                req1_category=ReqCategory.Throw,
                req_matched=False,
                req_deadlock=False,
            ),
            (st.ReqType.Smart_resume, st.ReqType.Smart_sync): ReqFlags(
                req0_category=ReqCategory.Throw,
                req1_category=ReqCategory.Handshake,
                req_matched=False,
                req_deadlock=False,
            ),
            (st.ReqType.Smart_resume, st.ReqType.Smart_wait): ReqFlags(
                req0_category=ReqCategory.Throw,
                req1_category=ReqCategory.Catch,
                req_matched=True,
                req_deadlock=False,
            ),
            (st.ReqType.Smart_sync, st.ReqType.Smart_send): ReqFlags(
                req0_category=ReqCategory.Handshake,
                req1_category=ReqCategory.Throw,
                req_matched=False,
                req_deadlock=False,
            ),
            (st.ReqType.Smart_sync, st.ReqType.Smart_recv): ReqFlags(
                req0_category=ReqCategory.Handshake,
                req1_category=ReqCategory.Catch,
                req_matched=False,
                req_deadlock=True,
            ),
            (st.ReqType.Smart_sync, st.ReqType.Smart_resume): ReqFlags(
                req0_category=ReqCategory.Handshake,
                req1_category=ReqCategory.Throw,
                req_matched=False,
                req_deadlock=False,
            ),
            (st.ReqType.Smart_sync, st.ReqType.Smart_sync): ReqFlags(
                req0_category=ReqCategory.Handshake,
                req1_category=ReqCategory.Handshake,
                req_matched=True,
                req_deadlock=False,
            ),
            (st.ReqType.Smart_sync, st.ReqType.Smart_wait): ReqFlags(
                req0_category=ReqCategory.Handshake,
                req1_category=ReqCategory.Catch,
                req_matched=False,
                req_deadlock=True,
            ),
            (st.ReqType.Smart_wait, st.ReqType.Smart_send): ReqFlags(
                req0_category=ReqCategory.Catch,
                req1_category=ReqCategory.Throw,
                req_matched=False,
                req_deadlock=False,
            ),
            (st.ReqType.Smart_wait, st.ReqType.Smart_recv): ReqFlags(
                req0_category=ReqCategory.Catch,
                req1_category=ReqCategory.Catch,
                req_matched=False,
                req_deadlock=True,
            ),
            (st.ReqType.Smart_wait, st.ReqType.Smart_resume): ReqFlags(
                req0_category=ReqCategory.Catch,
                req1_category=ReqCategory.Throw,
                req_matched=True,
                req_deadlock=False,
            ),
            (st.ReqType.Smart_wait, st.ReqType.Smart_sync): ReqFlags(
                req0_category=ReqCategory.Catch,
                req1_category=ReqCategory.Handshake,
                req_matched=False,
                req_deadlock=True,
            ),
            (st.ReqType.Smart_wait, st.ReqType.Smart_wait): ReqFlags(
                req0_category=ReqCategory.Catch,
                req1_category=ReqCategory.Catch,
                req_matched=False,
                req_deadlock=True,
            ),
        }

        req_flags = request_table[(req0, req1)]
        req0_confirm_at_unreg: bool = False
        req0_confirm_at_active: bool = False
        req0_confirm_immediately: bool = False
        req0_will_do_refresh: bool = False
        req0_request_issued: bool = False

        req1_delay_confirm: bool = True

        self.log_test_msg(f"{req_flags=}")

        if timeout_type == TimeoutType.TimeoutTrue:
            if (
                req0_when_req1_state[0] == st.ThreadState.Unregistered
                or req0_when_req1_state[0] == st.ThreadState.Registered
            ):
                if req_flags.req1_category != ReqCategory.Throw:
                    req1_timeout_type = TimeoutType.TimeoutTrue
                else:
                    if req1_lap < req0_when_req1_lap and req_flags.req_matched:
                        supress_req1 = True

            elif req0_when_req1_state[0] == st.ThreadState.Alive:
                if req0 == st.ReqType.Smart_sync:
                    req0_specific_args["sync_set_ack_remotes"] = req1_name
                if req0_when_req1_lap == req1_lap:
                    if req_flags.req_deadlock:
                        req0_specific_args["deadlock_remotes"] = {req1_name}
                        req1_specific_args["deadlock_remotes"] = {req0_name}
                    elif req_flags.req0_category == ReqCategory.Throw:
                        timeout_type = TimeoutType.TimeoutNone
                    elif (
                        req_flags.req1_category != ReqCategory.Throw
                        or req_flags.req_matched
                    ):
                        supress_req1 = True

                elif req0_when_req1_lap < req1_lap:
                    if req_flags.req0_category == ReqCategory.Throw:
                        timeout_type = TimeoutType.TimeoutNone
                    else:
                        if req_flags.req1_category != ReqCategory.Throw:
                            req1_timeout_type = TimeoutType.TimeoutTrue

                else:  # req1_lap < req0_when_req1_lap
                    if req_flags.req0_category == ReqCategory.Throw:
                        timeout_type = TimeoutType.TimeoutNone
                    else:
                        if req_flags.req_matched:
                            supress_req1 = True
                        elif req_flags.req1_category != ReqCategory.Throw:
                            req1_timeout_type = TimeoutType.TimeoutTrue

        # not an else since we might have cases where timeout_type True
        # was changed to None in the above section
        if timeout_type != TimeoutType.TimeoutTrue:
            if (
                req0_when_req1_state[0] == st.ThreadState.Unregistered
                or req0_when_req1_state[0] == st.ThreadState.Registered
            ) and req0_when_req1_state[1] == 0:
                if req0_when_req1_lap == req1_lap:
                    req0_stopped_remotes = {req1_name}
                    req0_will_do_refresh = True
                    if req_flags.req1_category != ReqCategory.Throw:
                        # since req0 will raise stopped error it will
                        # not be replying to req1 when req1 eventually
                        # gets active and does its request. So, req1
                        # will need to use timeout to prevent hang
                        req1_timeout_type = TimeoutType.TimeoutTrue
                elif req0_when_req1_lap < req1_lap:
                    req0_stopped_remotes = {req1_name}
                    req0_will_do_refresh = True
                    if req_flags.req1_category != ReqCategory.Throw:
                        req1_timeout_type = TimeoutType.TimeoutTrue
                elif req1_lap < req0_when_req1_lap:
                    if req_flags.req1_category != ReqCategory.Throw:
                        req1_timeout_type = TimeoutType.TimeoutTrue
                        # since req1 will issue its request during lap0
                        # and req0 will issue its request in lap1,
                        # req1 will timeout, and then continue to
                        # rotate into lap1 on through active where it
                        # will not issue a request and then to stopped.
                        # So, req0 will issue its request and then see
                        # that req1 went to stopped state.
                        req0_stopped_remotes = {req1_name}
                        req0_will_do_refresh = True
                    else:
                        # if req1 issues throw request and then stops,
                        # the request will remain pending for req0 when
                        # it issues its request. So, if req0 request
                        # matches, then req0 will succeed. If not
                        # matched, req0 will see req1 go to stopped
                        # state.
                        if req_flags.req_matched:
                            # if req1 is not registered then the del
                            # deferred flag will not be off
                            if req0_when_req1_state[0] != st.ThreadState.Registered:
                                # req0 will do the refresh because its
                                # delete was deferred in lap0 and now
                                # that it has satisfied its request in
                                # lap1 and cleared its pending reasons
                                # before req0 is registered (which
                                # clears the deferred delete flag in
                                # req0), it sees that it can do the
                                # refresh
                                req0_will_do_refresh = True

                            # we also need to confirm immediately before
                            # req1 is registered since that will clear
                            # the deferred delete flag and prevent req0
                            # from doing the refresh, or if already
                            # registered then we want to complete the
                            # request before req1 is stopped to avoid
                            # having del deferred being set on
                            req0_confirm_immediately = True

                            if req0 == st.ReqType.Smart_recv:
                                req0_specific_args["exp_senders"] = req1_name
                            elif req0 == st.ReqType.Smart_wait:
                                req0_specific_args["exp_resumers"] = req1_name
                        else:
                            req0_stopped_remotes = {req1_name}

                if req0_will_do_refresh:
                    pe = self.pending_events[req0_name]
                    ref_key: CallRefKey = req0.value

                    pe[PE.calling_refresh_msg][ref_key] += 1

                    req0_confirm_at_unreg = True

            elif (
                req0_when_req1_state[0] == st.ThreadState.Unregistered
                or req0_when_req1_state[0] == st.ThreadState.Registered
                or req0_when_req1_state[0] == st.ThreadState.Alive
            ):
                if req0 == st.ReqType.Smart_sync:
                    req0_specific_args["sync_set_ack_remotes"] = req1_name
                # if req1 is alive or will be alive before being
                # stopped, a throw req0 will always work regardless of
                # lap and regardless of whether the requests are matched
                if req_flags.req0_category == ReqCategory.Throw:
                    if req0 == st.ReqType.Smart_send:
                        req0_specific_args["exp_receivers"] = req1_name
                    elif req0 == st.ReqType.Smart_resume:
                        req0_specific_args["exp_resumed_targets"] = req1_name

                if req0_when_req1_lap == req1_lap:
                    if req_flags.req_deadlock:
                        req0_specific_args["deadlock_remotes"] = {req1_name}
                        req1_specific_args["deadlock_remotes"] = {req0_name}
                    else:
                        if req_flags.req0_category == ReqCategory.Throw:
                            if not req_flags.req_matched:
                                if req_flags.req1_category != ReqCategory.Throw:
                                    req1_timeout_type = TimeoutType.TimeoutTrue
                        else:
                            if req_flags.req_matched:
                                req0_confirm_at_active = True
                                if req0 == st.ReqType.Smart_recv:
                                    req0_specific_args["exp_senders"] = req1_name
                                elif req0 == st.ReqType.Smart_wait:
                                    req0_specific_args["exp_resumers"] = req1_name
                            else:
                                req0_stopped_remotes = {req1_name}
                                if req_flags.req1_category != ReqCategory.Throw:
                                    req1_timeout_type = TimeoutType.TimeoutTrue

                elif req0_when_req1_lap < req1_lap:
                    if req_flags.req0_category == ReqCategory.Throw:
                        # even though req0 does a throw, it will not
                        # persist as req1 rotates into stopped and is
                        # then resurrected. Req1 will need to request
                        # timeout since its catch request will not be
                        # matched
                        if req_flags.req1_category != ReqCategory.Throw:
                            req1_timeout_type = TimeoutType.TimeoutTrue
                    else:
                        req0_stopped_remotes = {req1_name}
                        if req_flags.req1_category != ReqCategory.Throw:
                            req1_timeout_type = TimeoutType.TimeoutTrue

                else:  # req1_lap < req0_when_req1_lap
                    if req_flags.req1_category == ReqCategory.Throw:
                        # req1 throw will persist
                        if req_flags.req_matched:
                            # if req1 is not registered then the del
                            # deferred flag will not be off
                            if req0_when_req1_state[0] == st.ThreadState.Unregistered:
                                # req0 will do the refresh because its
                                # delete was deferred in lap0 and now
                                # that it has satisfied its request in
                                # lap1 and cleared its pending reasons
                                # before req0 is registered (which
                                # clears the deferred delete flag in
                                # req0), it sees that it can do the
                                # refresh
                                req0_will_do_refresh = True

                            # we also need to confirm immediately before
                            # req1 is registered since that will clear
                            # the deferred delete flag and prevent req0
                            # from doing the refresh, or if already
                            # registered then we want to complete the
                            # request before req1 is stopped to avoid
                            # having del deferred being set on
                            req0_confirm_immediately = True
                            if req0 == st.ReqType.Smart_recv:
                                req0_specific_args["exp_senders"] = req1_name
                            elif req0 == st.ReqType.Smart_wait:
                                req0_specific_args["exp_resumers"] = req1_name
                        else:
                            if req_flags.req0_category != ReqCategory.Throw:
                                req0_stopped_remotes = {req1_name}
                    else:
                        req1_timeout_type = TimeoutType.TimeoutTrue
                        if req_flags.req0_category != ReqCategory.Throw:
                            req0_stopped_remotes = {req1_name}
                if req0_will_do_refresh:
                    pe = self.pending_events[req0_name]
                    ref_key = req0.value

                    pe[PE.calling_refresh_msg][ref_key] += 1

        if req0_when_req1_state[0] == st.ThreadState.Stopped:
            if req0_when_req1_lap == req1_lap:
                if req_flags.req1_category == ReqCategory.Throw:
                    if req_flags.req_matched:
                        if req0 == st.ReqType.Smart_recv:
                            req0_specific_args["exp_senders"] = req1_name
                        elif req0 == st.ReqType.Smart_wait:
                            req0_specific_args["exp_resumers"] = req1_name
                        if timeout_type == TimeoutType.TimeoutTrue:
                            timeout_type = TimeoutType.TimeoutNone
                    else:
                        req0_stopped_remotes = {req1_name}
                else:
                    req1_timeout_type = TimeoutType.TimeoutTrue
                    req0_stopped_remotes = {req1_name}
            elif req0_when_req1_lap < req1_lap:
                req0_stopped_remotes = {req1_name}
                if req_flags.req1_category != ReqCategory.Throw:
                    req1_timeout_type = TimeoutType.TimeoutTrue
            else:  # req1_lap < req0_when_req1_lap
                if req_flags.req1_category == ReqCategory.Throw:
                    if req_flags.req_matched:
                        if req0 == st.ReqType.Smart_recv:
                            req0_specific_args["exp_senders"] = req1_name
                        elif req0 == st.ReqType.Smart_wait:
                            req0_specific_args["exp_resumers"] = req1_name
                        if timeout_type == TimeoutType.TimeoutTrue:
                            timeout_type = TimeoutType.TimeoutNone
                    else:
                        req0_stopped_remotes = {req1_name}
                else:
                    req1_timeout_type = TimeoutType.TimeoutTrue
                    req0_stopped_remotes = {req1_name}

        ################################################################
        # lap loop
        ################################################################
        req0_confirm_parms = RequestConfirmParms(request_name="", serial_number=0)
        current_req1_state = st.ThreadState.Unregistered
        reg_iteration = 0
        for lap in range(2):
            ############################################################
            # start loop to advance receiver through the config states
            ############################################################
            for state in (
                st.ThreadState.Unregistered,
                st.ThreadState.Registered,
                st.ThreadState.Unregistered,
                st.ThreadState.Registered,
                st.ThreadState.Alive,
                st.ThreadState.Stopped,
            ):
                state_iteration = 0
                ########################################################
                # do join to make receiver unregistered
                ########################################################
                if state == st.ThreadState.Unregistered:
                    if current_req1_state == st.ThreadState.Registered:
                        self.add_cmd(
                            Unregister(
                                cmd_runners=self.commander_name,
                                unregister_targets=req1_name,
                            )
                        )
                        self.unregistered_names |= {req1_name}
                        state_iteration = 1

                        if req0_confirm_at_unreg and req0_request_issued:
                            self.add_cmd(
                                ConfirmResponse(
                                    cmd_runners=[self.commander_name],
                                    confirm_cmd=req0_confirm_parms.request_name,
                                    confirm_serial_num=req0_confirm_parms.serial_number,
                                    confirmers=req0_name,
                                )
                            )

                    elif current_req1_state == st.ThreadState.Stopped:
                        # pause to allow req0 to recognize that req1 is
                        # stopped so that it will have time to issue
                        # the raise error log message that the test code
                        # will intercept and use to reset
                        # request_pending in the test code before we
                        # start deleting req1 from the pair_array so
                        # that we determine the correct log messages to
                        # add for log verification
                        # if req0_stopped_remotes:
                        #     self.add_cmd(
                        #         Pause(cmd_runners=self.commander_name,
                        #               pause_seconds=1))
                        if req0_request_issued:
                            self.add_cmd(
                                ConfirmResponse(
                                    cmd_runners=[self.commander_name],
                                    confirm_cmd=req0_confirm_parms.request_name,
                                    confirm_serial_num=req0_confirm_parms.serial_number,
                                    confirmers=req0_name,
                                )
                            )
                        self.build_join_suite(
                            cmd_runners=self.commander_name,
                            join_target_names=req1_name,
                            validate_config=False,
                        )
                    current_req1_state = st.ThreadState.Unregistered
                ########################################################
                # do create to make receiver registered
                ########################################################
                elif state == st.ThreadState.Registered:
                    state_iteration = reg_iteration % 2
                    reg_iteration += 1
                    self.build_create_suite(
                        f1_create_items=[
                            F1CreateItem(
                                name=req1_name,
                                auto_start=False,
                                target_rtn=outer_f1,
                                app_config=AppConfig.ScriptStyle,
                            )
                        ],
                        validate_config=False,
                    )
                    current_req1_state = st.ThreadState.Registered
                ########################################################
                # do start to make req1 alive
                ########################################################
                elif state == st.ThreadState.Alive:
                    self.build_start_suite(start_names=req1_name, validate_config=False)

                    if req1_lap == lap:
                        if not supress_req1:
                            if req_flags.req1_category == ReqCategory.Throw:
                                # regardless of lap and regardless of
                                # whether the requests are matched, a
                                # throw from req1 to req0 will always
                                # complete successfully since req0 is
                                # always alive
                                if req1 == st.ReqType.Smart_send:
                                    req1_specific_args["exp_receivers"] = req0_name
                                elif req1 == st.ReqType.Smart_resume:
                                    req1_specific_args[
                                        "exp_resumed_targets"
                                    ] = req0_name
                            elif (
                                req1_timeout_type != TimeoutType.TimeoutTrue
                                and not req_flags.req_deadlock
                            ):
                                # req1 is doing a catch or handshake and
                                # if timeout was not requested then it
                                # will work
                                if req1 == st.ReqType.Smart_recv:
                                    req1_specific_args["exp_senders"] = req0_name
                                elif req1 == st.ReqType.Smart_wait:
                                    req1_specific_args["exp_resumers"] = req0_name
                                else:
                                    # exp_syncers not really used yet
                                    # but we will code a placeholder
                                    # here is case we do use it later
                                    req1_specific_args["exp_syncers"] = req0_name
                            req1_confirm_parms = request_build_rtns[req1](
                                timeout_type=req1_timeout_type,
                                cmd_runner=req1_name,
                                target=req0_name,
                                stopped_remotes=req1_stopped_remotes,
                                request_specific_args=req1_specific_args,
                            )
                            if not req1_delay_confirm:
                                self.add_cmd(
                                    ConfirmResponse(
                                        cmd_runners=self.commander_name,
                                        confirm_cmd=(req1_confirm_parms.request_name),
                                        confirm_serial_num=(
                                            req1_confirm_parms.serial_number
                                        ),
                                        confirmers=req1_name,
                                    )
                                )
                            if req0_confirm_at_active and req0_request_issued:
                                self.add_cmd(
                                    ConfirmResponse(
                                        cmd_runners=[self.commander_name],
                                        confirm_cmd=req0_confirm_parms.request_name,
                                        confirm_serial_num=(
                                            req0_confirm_parms.serial_number
                                        ),
                                        confirmers=req0_name,
                                    )
                                )
                        if supress_req1:  # or not req0_requires_ack:
                            req1_pause_time = 1
                            self.add_cmd(
                                Pause(
                                    cmd_runners=self.commander_name,
                                    pause_seconds=req1_pause_time,
                                )
                            )
                    current_req1_state = st.ThreadState.Alive
                ########################################################
                # do stop to make receiver stopped
                ########################################################
                else:  # state == st.ThreadState.Stopped:
                    self.build_exit_suite(
                        cmd_runner=self.commander_name,
                        names=req1_name,
                        validate_config=False,
                        reset_ops_count=reset_ops_count,
                    )
                    current_req1_state = st.ThreadState.Stopped
                ########################################################
                # issue req0
                ########################################################
                if (
                    req0_when_req1_state[0] == state
                    and req0_when_req1_state[1] == state_iteration
                    and req0_when_req1_lap == lap
                ):
                    if timeout_type == TimeoutType.TimeoutTrue:
                        pause_time: IntOrFloat = 1
                    else:
                        pause_time = 0.5
                    req0_confirm_parms = request_build_rtns[req0](
                        timeout_type=timeout_type,
                        cmd_runner=req0_name,
                        target=req1_name,
                        stopped_remotes=req0_stopped_remotes,
                        request_specific_args=req0_specific_args,
                    )

                    req0_request_issued = True
                    if req0_confirm_immediately:
                        self.add_cmd(
                            ConfirmResponse(
                                cmd_runners=[self.commander_name],
                                confirm_cmd=req0_confirm_parms.request_name,
                                confirm_serial_num=req0_confirm_parms.serial_number,
                                confirmers=req0_name,
                            )
                        )

                    self.add_cmd(
                        Pause(cmd_runners=self.commander_name, pause_seconds=pause_time)
                    )

        ################################################################
        # finally, confirm req0 is done
        ################################################################
        self.add_cmd(
            ConfirmResponse(
                cmd_runners=[self.commander_name],
                confirm_cmd=req0_confirm_parms.request_name,
                confirm_serial_num=req0_confirm_parms.serial_number,
                confirmers=req0_name,
            )
        )

        ################################################################
        # confirm req1 is done if delay confirm needed
        ################################################################
        if req1_delay_confirm and not supress_req1:
            self.add_cmd(
                ConfirmResponse(
                    cmd_runners=self.commander_name,
                    confirm_cmd=(req1_confirm_parms.request_name),
                    confirm_serial_num=(req1_confirm_parms.serial_number),
                    confirmers=req1_name,
                )
            )

    ####################################################################
    # build_send_msg_request
    ####################################################################
    def build_send_msg_request(
        self,
        timeout_type: TimeoutType,
        cmd_runner: str,
        target: str,
        stopped_remotes: set[str],
        request_specific_args: dict[str, Any],
    ) -> RequestConfirmParms:
        """Adds cmds to the cmd queue.

        Args:
            timeout_type: None, False, or True for timeout
            cmd_runner: name of thread that will do the request
            target: name of thread that is the target_rtn of the request
            stopped_remotes: names of threads that are expected to be
                detected by the request as stopped
            request_specific_args: specific args for each request

        Returns:
            the name and serial number of the request for confirmation
            purposes

        """
        timeout_time: IntOrFloat
        if timeout_type == TimeoutType.TimeoutNone:
            confirm_request_name = "SendMsg"
            request_serial_num = self.add_cmd(
                SendMsg(
                    cmd_runners=cmd_runner,
                    receivers=target,
                    exp_receivers={target} - stopped_remotes,
                    msgs_to_send=request_specific_args["sender_msgs"],
                    msg_idx=0,
                    stopped_remotes=stopped_remotes,
                )
            )
        elif timeout_type == TimeoutType.TimeoutFalse:
            confirm_request_name = "SendMsgTimeoutFalse"
            timeout_time = 6
            request_serial_num = self.add_cmd(
                SendMsgTimeoutFalse(
                    cmd_runners=cmd_runner,
                    receivers=target,
                    exp_receivers={target} - stopped_remotes,
                    msgs_to_send=request_specific_args["sender_msgs"],
                    msg_idx=0,
                    timeout=timeout_time,
                    stopped_remotes=stopped_remotes,
                )
            )
        else:  # timeout_type == TimeoutType.TimeoutTrue
            timeout_time = 0.5
            confirm_request_name = "SendMsgTimeoutTrue"
            request_serial_num = self.add_cmd(
                SendMsgTimeoutTrue(
                    cmd_runners=cmd_runner,
                    receivers=target,
                    exp_receivers=set(),
                    msgs_to_send=request_specific_args["sender_msgs"],
                    msg_idx=0,
                    timeout=timeout_time,
                    unreg_timeout_names=target,
                    fullq_timeout_names=[],
                    stopped_remotes=stopped_remotes,
                )
            )

        return RequestConfirmParms(
            request_name=confirm_request_name, serial_number=request_serial_num
        )

    ####################################################################
    # build_recv_msg_request
    ####################################################################
    def build_recv_msg_request(
        self,
        timeout_type: TimeoutType,
        cmd_runner: str,
        target: str,
        stopped_remotes: set[str],
        request_specific_args: dict[str, Any],
    ) -> RequestConfirmParms:
        """Adds cmds to the cmd queue.

        Args:
            timeout_type: None, False, or True for timeout
            cmd_runner: name of thread that will do the request
            target: name of thread that is the target_rtn of the request
            stopped_remotes: names of threads that are expected to be
                detected by the request as stopped
            request_specific_args: specific args for each request

        Returns:
            the name and serial number of the request for confirmation
            purposes

        """
        timeout_time: IntOrFloat
        if timeout_type == TimeoutType.TimeoutNone:
            confirm_request_name = "RecvMsg"
            request_serial_num = self.add_cmd(
                RecvMsg(
                    cmd_runners=cmd_runner,
                    senders=target,
                    exp_senders=request_specific_args["exp_senders"],
                    exp_msgs=request_specific_args["sender_msgs"],
                    stopped_remotes=stopped_remotes,
                    deadlock_remotes=request_specific_args["deadlock_remotes"],
                )
            )
        elif timeout_type == TimeoutType.TimeoutFalse:
            confirm_request_name = "RecvMsgTimeoutFalse"
            timeout_time = 6
            request_serial_num = self.add_cmd(
                RecvMsgTimeoutFalse(
                    cmd_runners=cmd_runner,
                    senders=target,
                    exp_senders=request_specific_args["exp_senders"],
                    exp_msgs=request_specific_args["sender_msgs"],
                    timeout=timeout_time,
                    stopped_remotes=stopped_remotes,
                    deadlock_remotes=request_specific_args["deadlock_remotes"],
                )
            )
        else:  # timeout_type == TimeoutType.TimeoutTrue
            # set timeout large enough to make sure we see stopped or
            # deadlock before we time out
            if stopped_remotes or request_specific_args["deadlock_remotes"]:
                timeout_time = 6
            else:
                timeout_time = 0.2
            confirm_request_name = "RecvMsgTimeoutTrue"
            request_serial_num = self.add_cmd(
                RecvMsgTimeoutTrue(
                    cmd_runners=cmd_runner,
                    senders=target,
                    exp_senders=request_specific_args["exp_senders"],
                    exp_msgs=request_specific_args["sender_msgs"],
                    timeout=timeout_time,
                    timeout_names=target,
                    stopped_remotes=stopped_remotes,
                    deadlock_remotes=request_specific_args["deadlock_remotes"],
                )
            )

        return RequestConfirmParms(
            request_name=confirm_request_name, serial_number=request_serial_num
        )

    ####################################################################
    # build_resume_request
    ####################################################################
    def build_resume_request(
        self,
        timeout_type: TimeoutType,
        cmd_runner: str,
        target: str,
        stopped_remotes: set[str],
        request_specific_args: dict[str, Any],
    ) -> RequestConfirmParms:
        """Adds cmds to the cmd queue.

        Args:
            timeout_type: None, False, or True for timeout
            cmd_runner: name of thread that will do the request
            target: name of thread that is the target_rtn of the request
            stopped_remotes: names of threads that are expected to be
                detected by the request as stopped
            request_specific_args: specific args for each request

        Returns:
            the name and serial number of the request for confirmation
            purposes

        """
        timeout_time: IntOrFloat
        if timeout_type == TimeoutType.TimeoutNone:
            confirm_request_name = "Resume"
            request_serial_num = self.add_cmd(
                Resume(
                    cmd_runners=cmd_runner,
                    targets=target,
                    exp_resumed_targets=request_specific_args["exp_resumed_targets"],
                    stopped_remotes=stopped_remotes,
                )
            )
        elif timeout_type == TimeoutType.TimeoutFalse:
            confirm_request_name = "ResumeTimeoutFalse"
            timeout_time = 6
            request_serial_num = self.add_cmd(
                ResumeTimeoutFalse(
                    cmd_runners=cmd_runner,
                    targets=target,
                    exp_resumed_targets=request_specific_args["exp_resumed_targets"],
                    timeout=timeout_time,
                    stopped_remotes=stopped_remotes,
                )
            )
        else:  # timeout_type == TimeoutType.TimeoutTrue
            timeout_time = 0.5
            confirm_request_name = "ResumeTimeoutTrue"
            request_serial_num = self.add_cmd(
                ResumeTimeoutTrue(
                    cmd_runners=cmd_runner,
                    targets=target,
                    exp_resumed_targets=request_specific_args["exp_resumed_targets"],
                    timeout=timeout_time,
                    timeout_names=target,
                    stopped_remotes=stopped_remotes,
                )
            )

        return RequestConfirmParms(
            request_name=confirm_request_name, serial_number=request_serial_num
        )

    ####################################################################
    # build_send_scenario
    ####################################################################
    def build_send_scenario(
        self, num_senders: int, num_receivers: int, num_msgs: int, send_type: SendType
    ) -> None:
        """Add cmds to run scenario.

        Args:
            num_senders: number of sender threads
            num_receivers: number of receiver threads
            num_msgs: number of message to send
            send_type: type of send to do

        """
        senders = get_names("sender_", num_senders)

        receivers = get_names("receiver_", num_receivers)

        self.create_config(active_names=senders | receivers)

        msgs_to_send = SendRecvMsgs(
            sender_names=senders,
            receiver_names=receivers,
            num_msgs=num_msgs,
            text="build_send_scenario",
        )

        ############################################################
        # send messages
        ############################################################
        for msg_idx in range(num_msgs):
            send_msg_serial_num = self.add_cmd(
                SendMsg(
                    cmd_runners=senders,
                    receivers=receivers,
                    exp_receivers=receivers,
                    msgs_to_send=msgs_to_send,
                    msg_idx=msg_idx,
                    send_type=send_type,
                )
            )
            self.add_cmd(
                ConfirmResponse(
                    cmd_runners=self.commander_name,
                    confirm_cmd="SendMsg",
                    confirm_serial_num=send_msg_serial_num,
                    confirmers=senders,
                )
            )

        ############################################################
        # receive messages
        ############################################################
        recv_msg_serial_num = self.add_cmd(
            RecvMsg(
                cmd_runners=receivers,
                senders=senders,
                exp_senders=senders,
                exp_msgs=msgs_to_send,
            )
        )
        self.add_cmd(
            ConfirmResponse(
                cmd_runners=self.commander_name,
                confirm_cmd="RecvMsg",
                confirm_serial_num=recv_msg_serial_num,
                confirmers=receivers,
            )
        )

    ####################################################################
    # build_send_resume_cnt_scenario
    ####################################################################
    def build_send_resume_cnt_scenario(
        self,
        request_type: st.ReqType,
        pre_count: int,
        num_count_0: int,
        num_count_1: int,
    ) -> None:
        """Add cmds to run scenario.

        Args:
            request_type: the request to do
            pre_count: the sender or resumer count for 0th batch
            num_count_0: the sender or resumer count for 1st batch
            num_count_1: the sender or resumer count for 2nd batch

        """
        num_senders_resumers = 5

        senders_resumers = get_names("sender_resumer_", num_senders_resumers)

        receiver_waiter = "receiver_waiter_0"

        self.create_config(active_names=senders_resumers | {receiver_waiter})

        msgs_to_send = SendRecvMsgs(
            sender_names=senders_resumers,
            receiver_names=receiver_waiter,
            num_msgs=1,
            text="build_send_resume_cnt_scenario",
        )

        ################################################################
        # build_send_request
        ################################################################
        def build_send_request() -> tuple[str, int]:
            """Add send request to run scenario."""
            request_to_confirm = "SendMsg"
            request_serial_num = self.add_cmd(
                SendMsg(
                    cmd_runners=sender_resumer,
                    receivers=receiver_waiter,
                    exp_receivers=receiver_waiter,
                    msgs_to_send=msgs_to_send,
                    msg_idx=0,
                )
            )

            return request_to_confirm, request_serial_num

        ################################################################
        # build_receive_request
        ################################################################
        def build_recv_request() -> tuple[str, int]:
            """Add receive request to run scenario."""
            if exp_timeout:
                request_to_confirm = "RecvMsgTimeoutTrue"
                request_serial_num = self.add_cmd(
                    RecvMsgTimeoutTrue(
                        cmd_runners=receiver_waiter,
                        senders=senders_resumers,
                        exp_senders=exp_senders_resumers,
                        exp_msgs=msgs_to_send,
                        timeout=1,
                        timeout_names=senders_resumers,
                        sender_count=sender_resumer_count,
                    )
                )
            else:
                request_to_confirm = "RecvMsg"
                request_serial_num = self.add_cmd(
                    RecvMsg(
                        cmd_runners=receiver_waiter,
                        senders=senders_resumers,
                        exp_senders=exp_senders_resumers,
                        exp_msgs=msgs_to_send,
                        sender_count=sender_resumer_count,
                    )
                )
            return request_to_confirm, request_serial_num

        ################################################################
        # build_resume_request
        ################################################################
        def build_resume_request() -> tuple[str, int]:
            """Add send request to run scenario."""
            request_to_confirm = "Resume"
            request_serial_num = self.add_cmd(
                Resume(
                    cmd_runners=sender_resumer,
                    targets=receiver_waiter,
                    exp_resumed_targets=receiver_waiter,
                )
            )
            return request_to_confirm, request_serial_num

        ################################################################
        # build_wait_request
        ################################################################
        def build_wait_request() -> tuple[str, int]:
            """Add wait request to run scenario."""
            if exp_timeout:
                request_to_confirm = "WaitTimeoutTrue"
                request_serial_num = self.add_cmd(
                    WaitTimeoutTrue(
                        cmd_runners=receiver_waiter,
                        resumers=senders_resumers,
                        exp_resumers=exp_senders_resumers,
                        timeout=1,
                        timeout_remotes=senders_resumers,
                        resumer_count=sender_resumer_count,
                    )
                )
            else:
                request_to_confirm = "Wait"
                request_serial_num = self.add_cmd(
                    Wait(
                        cmd_runners=receiver_waiter,
                        resumers=senders_resumers,
                        exp_resumers=exp_senders_resumers,
                        resumer_count=sender_resumer_count,
                    )
                )
            return request_to_confirm, request_serial_num

        requests: dict[st.ReqType, Callable[..., tuple[str, int]]] = {
            st.ReqType.Smart_send: build_send_request,
            st.ReqType.Smart_recv: build_recv_request,
            st.ReqType.Smart_resume: build_resume_request,
            st.ReqType.Smart_wait: build_wait_request,
        }

        exp_timeout = False
        sorted_senders_resumers: list[str] = sorted(senders_resumers)
        max_count = max(pre_count, num_count_0)
        if num_count_0:
            exp_senders_resumers: set[str] = set(sorted_senders_resumers[0:max_count])
            sender_resumer_count = num_count_0
        else:
            exp_senders_resumers = senders_resumers
            sender_resumer_count = None

        if request_type == st.ReqType.Smart_recv:
            sender_resumer_req_type = st.ReqType.Smart_send
        else:
            sender_resumer_req_type = st.ReqType.Smart_resume

        ################################################################
        # send or resume
        ################################################################
        recv_wait_confirm_0 = ""
        recv_wait_serial_num_0 = 0
        len_exp_senders_resumers = len(exp_senders_resumers)
        pause_secs = 0.4
        for idx, sender_resumer in enumerate(sorted(senders_resumers)):
            # issue recv/wait after pre_count requests
            if idx == pre_count:
                recv_wait_confirm_0, recv_wait_serial_num_0 = requests[request_type]()

            self.add_cmd(
                Pause(cmd_runners=self.commander_name, pause_seconds=pause_secs)
            )

            if len_exp_senders_resumers < idx:
                pause_secs = 0.1  # allow remaining sends to go faster

            send_resume_confirm_0, send_resume_serial_num_0 = requests[
                sender_resumer_req_type
            ]()

            self.add_cmd(
                ConfirmResponse(
                    cmd_runners=self.commander_name,
                    confirm_cmd=send_resume_confirm_0,
                    confirm_serial_num=send_resume_serial_num_0,
                    confirmers=sender_resumer,
                )
            )

        self.add_cmd(Pause(cmd_runners=self.commander_name, pause_seconds=0.5))

        if pre_count == num_senders_resumers:
            recv_wait_confirm_0, recv_wait_serial_num_0 = requests[request_type]()

        if recv_wait_serial_num_0:
            self.add_cmd(
                ConfirmResponse(
                    cmd_runners=self.commander_name,
                    confirm_cmd=recv_wait_confirm_0,
                    confirm_serial_num=recv_wait_serial_num_0,
                    confirmers=receiver_waiter,
                )
            )

        ################################################################
        # receive or wait 2nd batch
        ################################################################
        if num_count_1:
            sender_resumer_count = num_count_1
        else:
            sender_resumer_count = None

        if num_count_0 == 0:
            exp_senders_resumers = set()
            exp_timeout = True
        else:
            exp_senders_resumers = set(sorted_senders_resumers[max_count:])
            if num_count_1 == 0:
                exp_timeout = True
            else:
                if len(exp_senders_resumers) < num_count_1:
                    exp_timeout = True

        recv_wait_confirm_1, recv_wait_serial_num_1 = requests[request_type]()

        self.add_cmd(
            ConfirmResponse(
                cmd_runners=self.commander_name,
                confirm_cmd=recv_wait_confirm_1,
                confirm_serial_num=recv_wait_serial_num_1,
                confirmers=receiver_waiter,
            )
        )

    ####################################################################
    # build_recv_basic_scenario
    ####################################################################
    def build_recv_basic_scenario(
        self, num_senders: int, num_msgs: int, sender_count: int, recv_type: RecvType
    ) -> None:
        """Add cmds to run scenario.

        Args:
            num_senders: number of senders
            num_msgs: number of message to send
            sender_count: number of senders needed to satisfy smart_recv
            recv_type: type of recv to do

        """
        senders: set[str] = get_names(stem="sender_", count=num_senders)

        # non_senders are used to allow the smart_recv to specify a non
        # empty senders arg when there are no actual senders
        num_non_senders = 3
        non_senders: set[str] = get_names(stem="non_sender_", count=num_non_senders)

        receiver = "receiver_1"

        self.create_config(active_names=senders | non_senders | {receiver})

        # build msgs for non_senders since we might have no senders
        msgs_to_send = SendRecvMsgs(
            sender_names=senders | non_senders,
            receiver_names=receiver,
            num_msgs=num_msgs,
            text="build_recv_basic_scenario",
        )

        smt_recv_senders_arg: set[str] = set()
        if recv_type == RecvType.PartialSenders:
            num_smt_recv_senders_arg = len(senders) // 2
        elif recv_type == RecvType.MatchSenders:
            num_smt_recv_senders_arg = len(senders)
        elif recv_type == RecvType.ExtraSenders:
            num_smt_recv_senders_arg = len(senders)
            smt_recv_senders_arg |= non_senders
        else:  # recv_type == RecvType.UnmatchSenders:
            num_smt_recv_senders_arg = 0
            smt_recv_senders_arg |= non_senders

        for idx, sender_name in enumerate(senders):
            if num_smt_recv_senders_arg <= idx:
                break
            smt_recv_senders_arg |= {sender_name}

        # make sure we have a non-empty set for smart_recv in case
        # num_senders is zero or too small for PartialResumers to get
        # at least 1 sender
        if not smt_recv_senders_arg:
            smt_recv_senders_arg |= non_senders
        exp_senders: set[str] = senders & smt_recv_senders_arg

        recv_sender_count: Optional[int] = None
        if sender_count > 0:  # if we want sender_count
            # make sure we specify a legal value
            recv_sender_count = min(sender_count, len(smt_recv_senders_arg))

        ################################################################
        # send messages
        ################################################################
        if senders:
            for msg_idx in range(num_msgs):
                send_msg_serial_num = self.add_cmd(
                    SendMsg(
                        cmd_runners=senders,
                        receivers=receiver,
                        exp_receivers=receiver,
                        msgs_to_send=msgs_to_send,
                        msg_idx=msg_idx,
                        send_type=SendType.ToRemotes,
                    )
                )
                self.add_cmd(
                    ConfirmResponse(
                        cmd_runners=self.commander_name,
                        confirm_cmd="SendMsg",
                        confirm_serial_num=send_msg_serial_num,
                        confirmers=senders,
                    )
                )

        ################################################################
        # receive messages
        ################################################################
        timeout: int = 0
        timeout_remotes: set[str] = smt_recv_senders_arg - exp_senders
        if exp_senders:
            if recv_sender_count:
                if len(exp_senders) < recv_sender_count:
                    timeout = 1
            else:
                if smt_recv_senders_arg != exp_senders:
                    timeout = 1
        else:
            timeout = 1

        if timeout == 0:
            recv_msg_serial_num = self.add_cmd(
                RecvMsg(
                    cmd_runners=receiver,
                    senders=smt_recv_senders_arg,
                    exp_senders=exp_senders,
                    sender_count=recv_sender_count,
                    exp_msgs=msgs_to_send,
                )
            )
        else:
            recv_msg_serial_num = self.add_cmd(
                RecvMsgTimeoutTrue(
                    cmd_runners=receiver,
                    senders=smt_recv_senders_arg,
                    exp_senders=exp_senders,
                    sender_count=recv_sender_count,
                    timeout=1,
                    timeout_names=timeout_remotes,
                    exp_msgs=msgs_to_send,
                )
            )
        self.add_cmd(
            ConfirmResponse(
                cmd_runners=self.commander_name,
                confirm_cmd="RecvMsg",
                confirm_serial_num=recv_msg_serial_num,
                confirmers=receiver,
            )
        )

    ####################################################################
    # build_resume_basic_scenario
    ####################################################################
    def build_resume_basic_scenario(
        self, num_resumers: int, num_waiters: int, num_reg_waiters: int
    ) -> None:
        """Add cmds to run scenario.

        Args:
            num_resumers: number of resumer threads
            num_waiters: number of waiter threads
            num_reg_waiters: number of waiters to be registered at first

        """
        resumers: set[str] = get_names("resumer_", num_resumers)

        waiters: set[str] = get_names("waiter_", num_waiters)

        reg_waiters: set[str] = get_names("reg_waiter_", num_reg_waiters)

        self.create_config(reg_names=reg_waiters, active_names=resumers | waiters)

        targets: set[str] = waiters | reg_waiters

        ################################################################
        # resume
        ################################################################
        resume_serial_num = self.add_cmd(
            Resume(cmd_runners=resumers, targets=targets, exp_resumed_targets=targets)
        )

        # make sure resume is running and sees that reg_waiters are not
        # there yet. Note that we can't include waiters in the list of
        # timeout names because resume will set the wait_flag when it
        # sees that the targets (waiters) are alive - they don't need
        # to be waiting.
        self.add_cmd(
            WaitForRequestTimeouts(
                cmd_runners=self.commander_name,
                actor_names=resumers,
                timeout_names=reg_waiters,
            )
        )

        ################################################################
        # wait
        ################################################################
        wait_serial_num = self.add_cmd(
            Wait(cmd_runners=waiters, resumers=resumers, exp_resumers=resumers)
        )

        ################################################################
        # reg_wait
        ################################################################
        self.build_start_suite(start_names=reg_waiters, validate_config=False)
        reg_wait_serial_num = self.add_cmd(
            Wait(cmd_runners=reg_waiters, resumers=resumers, exp_resumers=resumers)
        )

        ################################################################
        # confirm response
        ################################################################
        self.add_cmd(
            ConfirmResponse(
                cmd_runners=self.commander_name,
                confirm_cmd="Resume",
                confirm_serial_num=resume_serial_num,
                confirmers=resumers,
            )
        )

        self.add_cmd(
            ConfirmResponse(
                cmd_runners=self.commander_name,
                confirm_cmd="Wait",
                confirm_serial_num=wait_serial_num,
                confirmers=waiters,
            )
        )

        self.add_cmd(
            ConfirmResponse(
                cmd_runners=self.commander_name,
                confirm_cmd="Wait",
                confirm_serial_num=reg_wait_serial_num,
                confirmers=reg_waiters,
            )
        )

        ################################################################
        # repeat in reverse
        ################################################################
        ################################################################
        # reg_wait
        ################################################################
        reg_wait_serial_num = self.add_cmd(
            Wait(cmd_runners=reg_waiters, resumers=resumers, exp_resumers=resumers)
        )

        ################################################################
        # wait
        ################################################################
        wait_serial_num = self.add_cmd(
            Wait(cmd_runners=waiters, resumers=resumers, exp_resumers=resumers)
        )

        ################################################################
        # resume
        ################################################################
        resume_serial_num = self.add_cmd(
            Resume(cmd_runners=resumers, targets=targets, exp_resumed_targets=targets)
        )

        ################################################################
        # confirm response
        ################################################################
        self.add_cmd(
            ConfirmResponse(
                cmd_runners=self.commander_name,
                confirm_cmd="Wait",
                confirm_serial_num=reg_wait_serial_num,
                confirmers=reg_waiters,
            )
        )

        self.add_cmd(
            ConfirmResponse(
                cmd_runners=self.commander_name,
                confirm_cmd="Wait",
                confirm_serial_num=wait_serial_num,
                confirmers=waiters,
            )
        )

        self.add_cmd(
            ConfirmResponse(
                cmd_runners=self.commander_name,
                confirm_cmd="Resume",
                confirm_serial_num=resume_serial_num,
                confirmers=resumers,
            )
        )

    ####################################################################
    # build_wait_basic_scenario
    ####################################################################
    def build_wait_basic_scenario(
        self, num_resumers: int, resumer_count: int, wait_type: WaitType
    ) -> None:
        """Add cmds to run scenario.

        Args:
            num_resumers: number of resumers beyond what is
                required for the wait_type_arg
            resumer_count: resumer_count specification for smart_wait
            wait_type: type of wait to do

        """
        resumers: set[str] = set()
        for idx in range(num_resumers):
            resumers |= {"resume_" + str(idx)}

        non_resumers: set[str] = set()
        for idx in range(3):
            non_resumers |= {"non_resumer_" + str(idx)}

        waiter = "waiter_1"

        self.create_config(active_names=resumers | non_resumers | {waiter})

        wait_resumers: set[str] = set()
        if wait_type == WaitType.PartialResumers:
            num_wait_resumers = len(resumers) // 2
        elif wait_type == WaitType.MatchResumers:
            num_wait_resumers = len(resumers)
        elif wait_type == WaitType.ExtraResumers:
            num_wait_resumers = len(resumers)
            wait_resumers |= non_resumers
        else:  # wait_type == WaitType.UnmatchResumers:
            num_wait_resumers = 0
            wait_resumers |= non_resumers

        for idx, resumer_name in enumerate(resumers):
            if num_wait_resumers <= idx:
                break
            wait_resumers |= {resumer_name}

        # make sure we have a non-empty set for smart_wait in case
        # num_resumers is zero or too small for PartialResumers to get
        # at least 1 resumer
        if not wait_resumers:
            wait_resumers |= non_resumers
        exp_resumers: set[str] = resumers & wait_resumers

        wait_resumer_count: Optional[int] = None
        if resumer_count > 0:  # if we want resumer_count
            # make sure we specify a legal value
            wait_resumer_count = min(resumer_count, len(wait_resumers))

        ################################################################
        # resume
        ################################################################
        if resumers:
            resume_serial_num = self.add_cmd(
                Resume(cmd_runners=resumers, targets=waiter, exp_resumed_targets=waiter)
            )

            ############################################################
            # confirm resumes are done
            ############################################################
            self.add_cmd(
                ConfirmResponse(
                    cmd_runners=self.commander_name,
                    confirm_cmd="Resume",
                    confirm_serial_num=resume_serial_num,
                    confirmers=resumers,
                )
            )

        ################################################################
        # wait
        ################################################################
        timeout: int = 0
        timeout_remotes: set[str] = wait_resumers - exp_resumers
        if exp_resumers:
            if wait_resumer_count:
                if len(exp_resumers) < wait_resumer_count:
                    timeout = 1
            else:
                if wait_resumers != exp_resumers:
                    timeout = 1
        else:
            timeout = 1

        if timeout == 0:
            cmd_to_confirm = "Wait"
            wait_serial_num = self.add_cmd(
                Wait(
                    cmd_runners=waiter,
                    resumers=wait_resumers,
                    resumer_count=wait_resumer_count,
                    exp_resumers=exp_resumers,
                )
            )
        else:
            cmd_to_confirm = "WaitTimeoutTrue"
            wait_serial_num = self.add_cmd(
                WaitTimeoutTrue(
                    cmd_runners=waiter,
                    resumers=wait_resumers,
                    resumer_count=wait_resumer_count,
                    exp_resumers=exp_resumers,
                    timeout=1,
                    timeout_remotes=timeout_remotes,
                )
            )

        ################################################################
        # confirm waits are done
        ################################################################
        self.add_cmd(
            ConfirmResponse(
                cmd_runners=self.commander_name,
                confirm_cmd=cmd_to_confirm,
                confirm_serial_num=wait_serial_num,
                confirmers=waiter,
            )
        )

    ####################################################################
    # build_sync_basic_scenario
    ####################################################################
    def build_sync_basic_scenario(self, num_syncers: int, num_extras: int) -> None:
        """Add cmds to run scenario.

        Args:
            num_syncers: number of threads doing sync
            num_extras: number of extra threads not involved in the
                sync request

        """
        syncers: set[str] = set()
        for idx in range(num_syncers):
            syncers |= {"syncer_" + str(idx)}

        extras: set[str] = set()
        for idx in range(num_extras):
            extras |= {"extra_" + str(idx)}

        self.create_config(active_names=syncers | extras)

        ################################################################
        # sync
        ################################################################
        sync_serial_num = self.add_cmd(
            Sync(cmd_runners=syncers, targets=syncers, sync_set_ack_remotes=syncers)
        )

        ################################################################
        # confirm response
        ################################################################
        self.add_cmd(
            ConfirmResponse(
                cmd_runners=self.commander_name,
                confirm_cmd="Sync",
                confirm_serial_num=sync_serial_num,
                confirmers=syncers,
            )
        )

    ####################################################################
    # build_sync_request
    ####################################################################
    def build_sync_request(
        self,
        timeout_type: TimeoutType,
        cmd_runner: str,
        target: str,
        stopped_remotes: set[str],
        request_specific_args: dict[str, Any],
    ) -> RequestConfirmParms:
        """Adds cmds to the cmd queue.

        Args:
            timeout_type: None, False, or True for timeout
            cmd_runner: name of thread that will do the request
            target: name of thread that is the target_rtn of the request
            stopped_remotes: names of threads that are expected to be
                detected by the request as stopped
            request_specific_args: specific args for each request

        Returns:
            the name and serial number of the request for confirmation
            purposes

        """
        timeout_time: IntOrFloat
        if timeout_type == TimeoutType.TimeoutNone:
            confirm_request_name = "Sync"
            request_serial_num = self.add_cmd(
                Sync(
                    cmd_runners=cmd_runner,
                    targets=target,
                    sync_set_ack_remotes=request_specific_args["sync_set_ack_remotes"],
                    stopped_remotes=stopped_remotes,
                    deadlock_remotes=request_specific_args["deadlock_remotes"],
                )
            )
        elif timeout_type == TimeoutType.TimeoutFalse:
            confirm_request_name = "SyncTimeoutFalse"
            timeout_time = 6
            request_serial_num = self.add_cmd(
                SyncTimeoutFalse(
                    cmd_runners=cmd_runner,
                    targets=target,
                    sync_set_ack_remotes=request_specific_args["sync_set_ack_remotes"],
                    timeout=timeout_time,
                    stopped_remotes=stopped_remotes,
                    deadlock_remotes=request_specific_args["deadlock_remotes"],
                )
            )
        else:  # timeout_type == TimeoutType.TimeoutTrue
            timeout_time = 0.5
            confirm_request_name = "SyncTimeoutTrue"
            request_serial_num = self.add_cmd(
                SyncTimeoutTrue(
                    cmd_runners=cmd_runner,
                    targets=target,
                    sync_set_ack_remotes=request_specific_args["sync_set_ack_remotes"],
                    timeout=timeout_time,
                    timeout_remotes=target,
                    stopped_remotes=stopped_remotes,
                    deadlock_remotes=request_specific_args["deadlock_remotes"],
                )
            )

        return RequestConfirmParms(
            request_name=confirm_request_name, serial_number=request_serial_num
        )

    ####################################################################
    # build_start_suite
    ####################################################################
    def build_start_suite(
        self, start_names: Iterable[str], validate_config: Optional[bool] = True
    ) -> None:
        """Return a list of ConfigCmd items for smart_unreg.

        Args:
            start_names: thread names to be started
            validate_config: indicates whether to validate the config

        """
        start_names = get_set(start_names)
        if not start_names.issubset(self.registered_names):
            raise InvalidInputDetected(
                f"Input {start_names} is not a subset "
                "of registered names "
                f"{self.registered_names}"
            )

        self.add_cmd(
            StartThread(cmd_runners=self.commander_name, start_names=start_names)
        )

        self.add_cmd(
            VerifyConfig(
                cmd_runners=self.commander_name,
                verify_type=VerifyType.VerifyAliveState,
                names_to_check=start_names,
            )
        )

        if validate_config:
            # self.add_cmd(ValidateConfig(cmd_runners=self.commander_name))
            self.add_cmd(
                VerifyConfig(
                    cmd_runners=self.commander_name,
                    verify_type=VerifyType.VerifyStructures,
                )
            )

        self.registered_names -= set(start_names)
        self.active_names |= set(start_names)

    ####################################################################
    # build_start_suite_num
    ####################################################################
    def build_start_suite_num(self, num_to_start: int) -> None:
        """Return a list of ConfigCmd items for smart_unreg.

        Args:
            num_to_start: number of threads to be started

        """
        assert num_to_start > 0
        if len(self.registered_names) < num_to_start:
            raise InvalidInputDetected(
                f"Input num_to_start {num_to_start} "
                f"is greater than the number of "
                f"registered threads "
                f"{len(self.registered_names)}"
            )

        names: list[str] = list(
            random.sample(sorted(self.registered_names), num_to_start)
        )

        return self.build_start_suite(start_names=names)

    ####################################################################
    # create_f1_thread
    ####################################################################
    def create_f1_thread(
        self,
        cmd_runner: str,
        target: Callable[[Any], None],
        name: str,
        app_config: AppConfig,
        auto_start: bool = True,
    ) -> None:
        """Create the f1_thread.

        Args:
            cmd_runner: name of thread doing the create
            target: the f1 routine that the thread will run
            name: name of the thread
            app_config: specifies the style of app to create
            auto_start: indicates whether the create should start the
                          thread
        """
        self.log_test_msg(f"create_f1_thread entry: {cmd_runner=}, " f"{name=}")
        self.f1_process_cmds[name] = True

        with self.ops_lock:
            self.monitor_pause += 1
        with self.monitor_condition:
            self.monitor_condition.wait()

        is_thread_target = False
        if app_config == AppConfig.ScriptStyle:
            is_thread_target = True

        if is_thread_target:
            thread_create: st.ThreadCreate = st.ThreadCreate.Target
        else:
            thread_create = st.ThreadCreate.Thread

        if auto_start:
            auto_start_decision: AutoStartDecision = AutoStartDecision.auto_start_yes
        else:
            auto_start_decision = AutoStartDecision.auto_start_no

        pe = self.pending_events[name]
        pe[PE.start_request].append(
            StartRequest(
                req_type=st.ReqType.Smart_init,
                targets={name},
                unreg_remotes=set(),
                not_registered_remotes=set(),
                timeout_remotes=set(),
                stopped_remotes=set(),
                deadlock_remotes=set(),
                eligible_targets=set(),
                completed_targets=set(),
                first_round_completed=set(),
                stopped_target_threads=set(),
                exp_senders=set(),
                exp_resumers=set(),
            )
        )

        req_key_entry: RequestKey = ("smart_init", "entry")

        pe[PE.request_msg][req_key_entry] += 1

        req_key_exit: RequestKey = ("smart_init", "exit")

        pe[PE.request_msg][req_key_exit] += 1

        if auto_start:
            pe[PE.start_request].append(
                StartRequest(
                    req_type=st.ReqType.Smart_start,
                    targets={name},
                    unreg_remotes=set(),
                    not_registered_remotes=set(),
                    timeout_remotes=set(),
                    stopped_remotes=set(),
                    deadlock_remotes=set(),
                    eligible_targets=set(),
                    completed_targets=set(),
                    first_round_completed=set(),
                    stopped_target_threads=set(),
                    exp_senders=set(),
                    exp_resumers=set(),
                )
            )
            req_key_entry = ("smart_start", "entry")

            pe[PE.request_msg][req_key_entry] += 1

            req_key_exit = ("smart_start", "exit")

            pe[PE.request_msg][req_key_exit] += 1

        if app_config == AppConfig.ScriptStyle:
            f1_thread = st.SmartThread(
                group_name=self.group_name,
                name=name,
                target_rtn=target,
                args=(name, self),
                auto_start=auto_start,
                max_msgs=self.max_msgs,
            )
        elif app_config == AppConfig.RemoteThreadApp:
            f1_outer_app = OuterF1ThreadApp(
                config_ver=self,
                name=name,
                auto_start=auto_start,
                max_msgs=self.max_msgs,
            )
            f1_thread = f1_outer_app.smart_thread
        else:
            raise UnrecognizedCmd(
                "create_f1_thread does not recognize " f"{app_config=}"
            )

        self.all_threads[name] = f1_thread
        # self.expected_registered[name].thread = f1_thread
        with self.ops_lock:
            self.expected_registered[name] = ThreadTracker(
                thread=f1_thread,
                is_alive=False,
                exiting=False,
                is_auto_started=auto_start,
                is_TargetThread=is_thread_target,
                exp_init_is_alive=False,
                exp_init_thread_state=st.ThreadState.Registered,
                thread_create=thread_create,
                auto_start_decision=auto_start_decision,
                # st_state=st.ThreadState.Unregistered,
                st_state=st.ThreadState.Initialized,
                found_del_pairs=defaultdict(int),
            )

        with self.ops_lock:
            self.monitor_pause -= 1

        self.cmd_waiting_event_items[cmd_runner] = threading.Event()

        self.wait_for_monitor(cmd_runner=cmd_runner, rtn_name="create_f1_thread")

        self.log_test_msg(f"create_f1_thread exiting: {cmd_runner=}, " f"{name=}")

    ####################################################################
    # exit_thread
    ####################################################################
    def exit_thread(self, cmd_runner: str, stopped_by: str) -> None:
        """Drive the commands received on the command queue.

        Args:
            cmd_runner: name of thread being stopped
            stopped_by: name of thread doing the stop

        """
        self.expected_registered[cmd_runner].stopped_by = stopped_by
        self.f1_process_cmds[cmd_runner] = False

    ####################################################################
    # f1_driver
    ####################################################################
    def f1_driver(self, f1_name: str) -> None:
        """Drive the commands received on the command queue.

        Args:
            f1_name: name of thread doing the command

        """
        self.log_ver.add_call_seq(
            name="f1_driver", seq="test_smart_thread.py::ConfigVerifier.f1_driver"
        )

        # We will stay in this loop to process command while the
        # f1_process_cmds dictionary entry for f1_name is True. The
        # ConfigCmdExitThread cmd runProcess method will simply set the
        # dictionary entry for f1_name to False so that we will then
        # exit after we indicate that the cmd is complete
        while self.f1_process_cmds[f1_name]:
            cmd: ConfigCmd = self.msgs.get_msg(f1_name, timeout=None)

            try:
                cmd.run_process(cmd_runner=f1_name)
            except Exception as exc:
                self.log_test_msg(f"f1_driver detected exception {exc}")
                self.abort_test_case()
                raise

            self.completed_cmds[f1_name].append(cmd.serial_num)

    ####################################################################
    # get_log_msg
    ####################################################################
    def get_log_msg(
        self,
        search_msg: str,
        skip_num: int = 0,
        start_idx: int = 0,
        end_idx: int = -1,
        reverse_search: bool = False,
    ) -> tuple[str, int]:
        """Search for a log message and return it.

        Args:
            search_msg: log message to search for as a regex
            skip_num: number of matches to skip
            start_idx: index from which to start
            end_idx: index of 1 past the index at which to stop
            reverse_search: indicates whether to search from the bottom

        Returns:
            the log message if found, otherwise an empty string
        """
        search_pattern = re.compile(search_msg)
        num_skipped = 0
        work_log = self.caplog_to_use.record_tuples.copy()

        if end_idx == -1:
            end_idx = len(work_log)

        work_log = work_log[start_idx:end_idx]
        if reverse_search:
            work_log.reverse()

        for idx, log_tuple in enumerate(work_log):
            if search_pattern.match(log_tuple[2]):
                if num_skipped == skip_num:
                    if reverse_search:
                        ret_idx = start_idx + (len(work_log) - idx) - 1
                    else:
                        ret_idx = start_idx + idx
                    return log_tuple[2], ret_idx
                num_skipped += 1

        return "", -1

    ####################################################################
    # get_log_msgs
    ####################################################################
    def get_log_msgs(self) -> bool:
        """Search for a log messages and return them in order.

        Returns:
            True, if messages were found, False otherwise
        """
        # we should never call with a non-empty deque
        assert not self.log_found_items

        with log_lock:
            work_log = self.caplog_to_use.record_tuples.copy()

        end_idx = len(work_log)

        # return if no new log message have been issued since last call
        if self.log_start_idx >= end_idx:
            return False

        work_log = work_log[self.log_start_idx : end_idx]

        for idx, log_tuple in enumerate(work_log, self.log_start_idx):
            for log_search_item in self.log_search_items:
                if log_search_item.search_pattern.match(log_tuple[2]):
                    found_log_item = log_search_item.get_found_log_item(
                        found_log_msg=log_tuple[2], found_log_idx=idx
                    )
                    self.log_found_items.append(found_log_item)

        # update next starting point
        self.log_start_idx = end_idx

        if self.log_found_items:
            return True
        else:
            return False

    ####################################################################
    # wait_for_monitor
    ####################################################################
    def wait_for_monitor(self, cmd_runner: str, rtn_name: str) -> None:
        """Start the named thread.

        Args:
            cmd_runner: thread doing the starts
            rtn_name: name of rtn that will wait

        """
        start_time = time.time()
        self.log_test_msg(f"wait_for_monitor {cmd_runner=} {rtn_name=}")
        with self.ops_lock:
            self.cmd_waiting_event_items[cmd_runner] = threading.Event()
        self.log_test_msg(
            f"{cmd_runner=} ({self.group_name}) {rtn_name} waiting for monitor "
            f"{start_time=}"
        )
        self.monitor_event.set()
        if self.cmd_waiting_event_items[cmd_runner].wait(timeout=120):
            with self.ops_lock:
                del self.cmd_waiting_event_items[cmd_runner]
        else:
            error_msg = (
                f"wait_for_monitor timed out for {cmd_runner=} ({self.group_name}) "
                f"and {rtn_name=} {start_time=}"
            )
            self.log_test_msg(error_msg)
            raise CmdTimedOut(error_msg)

    ####################################################################
    # log_name_groups
    ####################################################################
    def log_name_groups(self) -> None:
        """Issue log msgs to show the names in each set."""
        log_msg = f"unregistered_names: {sorted(self.unregistered_names)}"
        self.log_ver.add_msg(log_msg=re.escape(log_msg))
        logger.debug(log_msg)

        log_msg = f"registered_names:   {sorted(self.registered_names)}"
        self.log_ver.add_msg(log_msg=re.escape(log_msg))
        logger.debug(log_msg)

        log_msg = f"active_names:       {sorted(self.active_names)}"
        self.log_ver.add_msg(log_msg=re.escape(log_msg))
        logger.debug(log_msg)

        log_msg = f"stopped_remotes:    {sorted(self.stopped_remotes)}"
        self.log_ver.add_msg(log_msg=re.escape(log_msg))
        logger.debug(log_msg)

    ####################################################################
    # log_test_msg
    ####################################################################
    def log_test_msg(self, log_msg: str) -> None:
        """Issue log msgs for test rtn.

        Args:
            log_msg: the message to log

        """
        if (
            self.allow_log_test_msg
            or "waiting for monitor" in log_msg
            or "has been stopped by" in log_msg
            or "Monitor Checkpoint" in log_msg
            or "OuterF1ThreadApp.run() exit: " in log_msg
            or "outer_f1 exit: " in log_msg
            or "abort" in log_msg
            or "main_driver detected exception" in log_msg
        ):
            self.log_ver.add_msg(log_msg=re.escape(log_msg))
            logger.debug(log_msg, stacklevel=2)

    ####################################################################
    # main_driver
    ####################################################################
    def main_driver(self) -> None:
        """Drive the config commands for the test scenario."""
        self.log_ver.add_call_seq(
            name="main_driver", seq="test_smart_thread.py::ConfigVerifier.main_driver"
        )
        self.log_test_msg(f"main_driver entry: {self.group_name=}")
        while self.cmd_suite and not self.test_case_aborted:
            cmd: ConfigCmd = self.cmd_suite.popleft()
            self.log_test_msg(f"config_cmd: {self.group_name} {cmd}")

            if not cmd.cmd_runners:
                raise InvalidInputDetected(
                    "main_driver detected an empty set of cmd_runners"
                )
            for name in cmd.cmd_runners:
                if name == self.commander_name:
                    continue
                self.msgs.queue_msg(target=name, msg=cmd)

            if self.commander_name in cmd.cmd_runners:
                try:
                    # logger.debug(
                    #     f"TestDebug {self.commander_name} ({self.group_name}) "
                    #     f"testcase main driver calling run_process {cmd.run_process}"
                    # )
                    cmd.run_process(cmd_runner=self.commander_name)
                    # logger.debug(
                    #     f"TestDebug {self.commander_name} ({self.group_name}) "
                    #     f"testcase main driver back from run_process "
                    #     f"{cmd.run_process}"
                    # )
                except Exception as exc:
                    self.log_test_msg(f"main_driver detected exception {exc}")
                    self.abort_test_case()

                self.completed_cmds[self.commander_name].append(cmd.serial_num)

        logger.debug(
            f"TestDebug {self.commander_name} ({self.group_name}) testcase "
            "preparing to exit main_driver"
        )
        if not self.test_case_aborted:
            ############################################################
            # check that pending events are complete
            ############################################################
            self.log_test_msg(
                f"Monitor Checkpoint: check_pending_events {self.group_name} 42"
            )
            self.monitor_event.set()
            self.check_pending_events_complete_event.wait(timeout=30)

        names_to_join = st.SmartThread.get_smart_thread_names(
            group_name=self.group_name,
            states=(st.ThreadState.Alive, st.ThreadState.Stopped),
        )

        names_to_join -= {self.commander_name}
        if names_to_join:
            join_cmd = JoinTimeoutFalse(
                cmd_runners=self.commander_name, join_names=names_to_join, timeout=120
            )
            self.add_cmd_info(join_cmd)
            join_cmd.run_process(cmd_runner=self.commander_name)

        names_to_unreg = st.SmartThread.get_smart_thread_names(
            group_name=self.group_name
        )

        self.monitor_event.set()

        if names_to_unreg:
            unreg_cmd = Unregister(
                cmd_runners=self.commander_name,
                unregister_targets=names_to_unreg,
                post_main_driver=True,
            )
            self.add_cmd_info(unreg_cmd)
            unreg_cmd.run_process(cmd_runner=self.commander_name)

        self.monitor_event.set()

        self.main_driver_unreg.wait()

        self.monitor_exit = True
        self.monitor_event.set()
        self.monitor_thread.join()

        # if self.test_case_aborted:
        #     with open(path_to_file, 'w') as file:

        assert not self.test_case_aborted

        self.log_test_msg(f"main_driver exit: {self.group_name=}")

    ####################################################################
    # stop_thread
    ####################################################################
    def stop_thread(
        self,
        cmd_runner: str,
        stop_names: set[str],
        reset_ops_count: bool = False,
        send_recv_msgs: Optional[SendRecvMsgs] = None,
    ) -> None:
        """Start the named thread.

        Args:
            cmd_runner: name of thread doing the stop thread
            stop_names: names of the threads to stop
            reset_ops_count: specifies whether to set the
                pending_ops_count to zero
            send_recv_msgs: contains messages sent to stop_names
        """
        self.log_test_msg(f"{cmd_runner=} stop_thread entry for {stop_names=}")

        self.stopped_event_items[cmd_runner] = MonitorEventItem(
            client_event=threading.Event(), targets=stop_names.copy()
        )

        for stop_name in stop_names:
            self.stopping_names.append(stop_name)
            if stop_name not in self.pending_events:
                raise InvalidConfigurationDetected(
                    "stop_thread detected missing pending transition "
                    f"for {stop_name}: {self.pending_events=}"
                )
            if stop_name not in self.expected_registered:
                raise InvalidConfigurationDetected(
                    f"stop_thread attempting to stop {stop_name} which is "
                    f"not in the registry: {self.expected_registered=}"
                )

            self.monitor_event.set()
            exit_cmd = ExitThread(cmd_runners=stop_name, stopped_by=cmd_runner)
            self.add_cmd_info(exit_cmd)
            self.msgs.queue_msg(target=stop_name, msg=exit_cmd)

        work_names = stop_names.copy()
        while work_names:
            for stop_name in work_names:
                if not self.all_threads[stop_name].thread.is_alive():
                    self.log_test_msg(
                        f"{stop_name} ({self.group_name}) has been stopped by "
                        f"{cmd_runner}"
                    )
                    self.monitor_event.set()
                    if send_recv_msgs:
                        send_recv_msgs.clear_all_exp_msgs_received(stop_name)
                    if reset_ops_count:
                        with self.ops_lock:
                            for pair_key in self.expected_pairs.keys():
                                if stop_name in pair_key:
                                    self.expected_pairs[pair_key][
                                        stop_name
                                    ].reset_ops_count = True
                    work_names -= {stop_name}
                    break
                time.sleep(0.05)

        self.monitor_event.set()
        # we can not use wait_for_monitor because stop uses
        # stopped_event_items

        self.log_test_msg(
            f"{cmd_runner=} ({self.group_name}) stop_thread waiting for monitor"
        )
        self.monitor_event.set()
        if not self.stopped_event_items[cmd_runner].client_event.wait(timeout=60):
            self.abort_all_f1_threads()

        self.log_test_msg(f"{cmd_runner=} stop_thread exiting for " f"{stop_names=}")

    ####################################################################
    # verify_config
    ####################################################################
    def verify_config(self, verify_idx: int) -> None:
        """Verify that the SmartThread config is correct.

        Args:
            verify_idx: index for the saved snapshot data
        """
        verify_data: VerifyData = self.snap_shot_data[verify_idx].verify_data

        actions: dict[VerifyType, Callable[..., None]] = {
            VerifyType.VerifyStructures: self.verify_structures,
            VerifyType.VerifyAlive: self.verify_alive,
            VerifyType.VerifyNotAlive: self.verify_not_alive,
            VerifyType.VerifyState: self.verify_state,
            VerifyType.VerifyInRegistry: self.verify_in_registry,
            VerifyType.VerifyNotInRegistry: self.verify_not_in_registry,
            VerifyType.VerifyAliveState: self.verify_active_state,
            VerifyType.VerifyRegisteredState: self.verify_registered_state,
            VerifyType.VerifyStoppedState: self.verify_stopped_state,
            VerifyType.VerifyPaired: self.verify_paired,
            VerifyType.VerifyNotPaired: self.verify_not_paired,
            VerifyType.VerifyHalfPaired: self.verify_half_paired,
            VerifyType.VerifyPendingFlags: self.verify_pending_flags,
        }
        actions[verify_data.verify_type](
            real_reg_items=self.snap_shot_data[verify_idx].registry_items,
            real_pair_array_items=self.snap_shot_data[verify_idx].pair_array_items,
            verify_data=verify_data,
        )

    ####################################################################
    # verify_structures
    ####################################################################
    def verify_structures(
        self,
        real_reg_items: RegistryItems,
        real_pair_array_items: PairArrayItems,
        verify_data: VerifyData,
    ) -> None:
        """Verify that the SmartThread config is correct.

        Args:
            real_reg_items: snapshot of real registry items
            real_pair_array_items: snapshot of real pair array
            verify_data: contains data items used for the verification

        Raises:
            InvalidConfigurationDetected: validate_config has found a
            mismatch between the real and mock configuration

        """
        for name, real_reg_item in real_reg_items.items():
            if name not in self.expected_registered:
                raise InvalidConfigurationDetected(
                    f"verify_config found SmartThread real registry has entry "
                    f"for {name=} that is missing from the expected_registry. "
                    f"{self.expected_registered.keys()=}"
                )
            if self.expected_registered[name].is_alive != real_reg_item.is_alive:
                raise InvalidConfigurationDetected(
                    f"verify_config found SmartThread real registry has "
                    f"entry for {name=} {self.group_name} that has is_alive of "
                    f"{real_reg_item.is_alive} which does not match the "
                    f"expected_registered is_alive of "
                    f"{self.expected_registered[name].is_alive}"
                )
            if self.expected_registered[name].st_state != real_reg_item.state:
                raise InvalidConfigurationDetected(
                    f"verify_config found SmartThread real registry has "
                    f"entry for {name=} that has status of "
                    f"{real_reg_item.state} which does not match the "
                    f"mock expected_registered status of "
                    f"{self.expected_registered[name].st_state}"
                )

        # verify expected_registered matches real registry
        for name, tracker in self.expected_registered.items():
            if name not in real_reg_items:
                raise InvalidConfigurationDetected(
                    f"verify_config found expected_registered has an entry "
                    f"for {name=} that is missing from real "
                    f"SmartThread._registry"
                )

        # verify pair_array matches expected_pairs
        for pair_key, status_blocks in real_pair_array_items.items():
            if len(status_blocks) == 0:
                raise InvalidConfigurationDetected(
                    f"verify_config found pair_key {pair_key} in real "
                    f"SmartThread pair_array that has an empty status_blocks"
                )
            if pair_key not in self.expected_pairs:
                raise InvalidConfigurationDetected(
                    f"verify_config found pair_key {pair_key} in real "
                    f"SmartThread pair_array that is not found in "
                    f"expected_pairs"
                )
            for name, status_item in status_blocks.items():
                if name not in real_reg_items:
                    raise InvalidConfigurationDetected(
                        f"verify_config found SmartThread real pair_array "
                        f"has a status_blocks entry for {name=} that is "
                        f"missing from the real registry. "
                    )

                if name not in self.expected_registered:
                    raise InvalidConfigurationDetected(
                        f"verify_config found {name=} in real "
                        f"SmartThread pair_array status_blocks for pair_key"
                        f" {pair_key}, but is missing in mock "
                        f"expected_registered"
                    )

                if name not in self.expected_pairs[pair_key].keys():
                    raise InvalidConfigurationDetected(
                        f"verify_config found {name=} in real "
                        f"SmartThread pair_array status_blocks for pair_key"
                        f" {pair_key}, but is missing in expected_pairs"
                    )

                if len(status_blocks) == 1:
                    if not (
                        status_item.del_def_flag
                        or status_item.pending_request
                        or status_item.pending_msg_count
                        or status_item.pending_wait
                        or status_item.pending_sync
                    ):
                        raise InvalidConfigurationDetected(
                            f"verify_config found {name=} in real "
                            f"SmartThread pair_array status_blocks for "
                            f"pair_key {pair_key}, but it is a single "
                            f"name that has no pending reasons and is not "
                            f"del_deferred"
                        )
                mock_status_item = self.expected_pairs[pair_key][name]
                if status_item.pending_request != mock_status_item.pending_request:
                    raise InvalidConfigurationDetected(
                        f"verify_config found {name=} in real "
                        f"SmartThread pair_array status_blocks for "
                        f"pair_key {pair_key} has "
                        f"{status_item.pending_request=} which does not "
                        f"match {mock_status_item.pending_request=}"
                    )
                if status_item.pending_msg_count != mock_status_item.pending_msg_count:
                    raise InvalidConfigurationDetected(
                        f"verify_config found {name=} in real "
                        f"SmartThread pair_array status_blocks for "
                        f"pair_key {pair_key} has "
                        f"{status_item.pending_msg_count=} which does not "
                        f"match {mock_status_item.pending_msg_count=}"
                    )
                if status_item.pending_wait != mock_status_item.pending_wait:
                    raise InvalidConfigurationDetected(
                        f"verify_config found {name=} in real "
                        f"SmartThread pair_array status_blocks for "
                        f"pair_key {pair_key} has "
                        f"{status_item.pending_wait=} which does not "
                        f"match {mock_status_item.pending_wait=}"
                    )
                if status_item.pending_sync != mock_status_item.pending_sync:
                    raise InvalidConfigurationDetected(
                        f"verify_config found {name=} in real "
                        f"SmartThread pair_array status_blocks for "
                        f"pair_key {pair_key} has "
                        f"{status_item.pending_sync=} which does not "
                        f"match {mock_status_item.pending_sync=}"
                    )

        # verify expected_pairs matches pair_array
        for pair_key, mock_status_blocks in self.expected_pairs.items():
            if pair_key not in real_pair_array_items:
                raise InvalidConfigurationDetected(
                    f"verify_config found {pair_key=} in expected_pairs but "
                    f"not in real SmartThread pair_array"
                )
            for name, mock_status_item in mock_status_blocks.items():
                if name not in real_reg_items:
                    raise InvalidConfigurationDetected(
                        f"verify_config found SmartThread mock pair_array "
                        f"has a status_blocks entry for {name=} that is "
                        f"missing from the real registry. "
                    )

                if name not in self.expected_registered:
                    raise InvalidConfigurationDetected(
                        f"verify_config found {name=} in mock "
                        f"pair_array status_blocks for pair_key"
                        f" {pair_key}, but is missing in "
                        f"mock expected_registered"
                    )

                if name not in real_pair_array_items[pair_key]:
                    raise InvalidConfigurationDetected(
                        f"verify_config found {name=} in mock "
                        f"expected_pairs for pair_key {pair_key}, but not in "
                        "real SmartThread pair_array status_blocks"
                    )


########################################################################
# CommanderCurrentApp class
########################################################################
class CommanderCurrentApp:
    """Outer thread app for test."""

    def __init__(self, config_ver: ConfigVerifier, name: str, max_msgs: int) -> None:
        """Initialize the object.

        Args:
            config_ver: configuration verifier and test support methods
            name: name of thread
            max_msgs: max number of messages for msg_q

        """
        self.config_ver = config_ver
        self.smart_thread = st.SmartThread(
            group_name=config_ver.group_name,
            name=name,
            auto_start=False,
            max_msgs=max_msgs,
        )

    def run(self) -> None:
        """Run the test."""
        self.config_ver.main_driver()


########################################################################
# OuterThreadApp class
########################################################################
class OuterThreadApp(threading.Thread):
    """Outer thread app for test."""

    def __init__(
        self,
        config_ver: ConfigVerifier,
        name: str,
        # auto_start: bool,
        max_msgs: int,
    ) -> None:
        """Initialize the object.

        Args:
            config_ver: configuration verifier and test support methods
            name: name of thread
            max_msgs: max number of messages for msg_q

        """
        super().__init__()
        # threading.current_thread().name = name
        self.config_ver = config_ver
        self.smart_thread = st.SmartThread(
            group_name=config_ver.group_name,
            name=name,
            thread=self,
            auto_start=False,
            max_msgs=max_msgs,
        )

        # self.config_ver.commander_thread = self.smart_thread

    def run(self) -> None:
        """Run the test."""
        self.config_ver.log_ver.add_call_seq(
            name="smart_start", seq="test_smart_thread.py::OuterThreadApp.run"
        )

        self.config_ver.monitor_event.set()

        self.config_ver.main_driver()


########################################################################
# OuterSmartThreadApp class
########################################################################
class OuterSmartThreadApp(st.SmartThread, threading.Thread):
    """Outer thread app for test with both thread and SmartThread."""

    def __init__(self, config_ver: ConfigVerifier, name: str, max_msgs: int) -> None:
        """Initialize the object.

        Args:
            config_ver: configuration verifier and test support methods
            name: name of thread
            max_msgs: max number of messages for msg_q

        """
        # super().__init__()
        threading.Thread.__init__(self)
        threading.current_thread().name = name
        st.SmartThread.__init__(
            self,
            group_name=config_ver.group_name,
            name=name,
            thread=self,
            auto_start=False,
            max_msgs=max_msgs,
        )
        self.config_ver = config_ver
        # self.config_ver.commander_thread = self

    def run(self) -> None:
        """Run the test."""
        self.config_ver.main_driver()


########################################################################
# OuterSmartThreadApp2 class
########################################################################
class OuterSmartThreadApp2(threading.Thread, st.SmartThread):
    """Outer thread app for test with both thread and SmartThread."""

    def __init__(self, config_ver: ConfigVerifier, name: str, max_msgs: int) -> None:
        """Initialize the object.

        Args:
            config_ver: configuration verifier and test support methods
            name: name of thread
            max_msgs: max number of messages for msg_q

        """
        # super().__init__()
        threading.Thread.__init__(self)
        threading.current_thread().name = name
        st.SmartThread.__init__(
            self,
            group_name=config_ver.group_name,
            name=name,
            thread=self,
            auto_start=False,
            max_msgs=max_msgs,
        )
        self.config_ver = config_ver
        # self.config_ver.commander_thread = self

    def run(self) -> None:
        """Run the test."""
        self.config_ver.main_driver()


########################################################################
# OuterF1ThreadApp class
########################################################################
class OuterF1ThreadApp(threading.Thread):
    """Outer thread app for test."""

    def __init__(
        self, config_ver: ConfigVerifier, name: str, auto_start: bool, max_msgs: int
    ) -> None:
        """Initialize the object.

        Args:
            config_ver: configuration verifier and test support methods
            name: name of thread
            auto_start: True, start thread
            max_msgs: max number of messages for msg_q

        """
        super().__init__()
        self.config_ver = config_ver
        self.name = name
        self.smart_thread = st.SmartThread(
            group_name=config_ver.group_name,
            name=name,
            thread=self,
            # auto_start=False,
            auto_start=auto_start,
            max_msgs=max_msgs,
        )

    def run(self) -> None:
        """Run the test."""
        self.config_ver.log_test_msg(f"OuterF1ThreadApp.run() entry: {self.name}")

        # self.config_ver.f1_driver(f1_name=self.smart_thread.name)
        self.config_ver.f1_driver(f1_name=self.name)

        ################################################################
        # exit
        ################################################################
        self.config_ver.log_test_msg(
            f"OuterF1ThreadApp.run() exit: {self.name} "
            f"({self.config_ver.group_name})"
        )


########################################################################
# outer_f1
########################################################################
def outer_f1(f1_name: str, f1_config_ver: ConfigVerifier) -> None:
    """Target routine in the outer scope.

    Args:
        f1_name: thread name
        f1_config_ver: configuration verifier instance

    """
    f1_config_ver.log_test_msg(f"outer_f1 entry: {f1_name}")

    f1_config_ver.f1_driver(f1_name=f1_name)

    ####################################################################
    # exit
    ####################################################################
    f1_config_ver.log_test_msg(
        f"outer_f1 exit: {f1_name} " f"({f1_config_ver.group_name})"
    )


########################################################################
# commander_config
########################################################################
commander_config: dict[int, AppConfig] = {
    0: AppConfig.ScriptStyle,
    1: AppConfig.CurrentThreadApp,
    2: AppConfig.RemoteThreadApp,
    3: AppConfig.RemoteSmartThreadApp,
    4: AppConfig.RemoteSmartThreadApp2,
}

num_commander_configs = len(commander_config)
