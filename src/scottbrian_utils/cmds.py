"""Module cmds.

====
Cmds
====

The Cmds class can be used during testing to send message between
threads, set a timer, or pause for a certain amount of time.

:Example: send cmd message to remote thread

>>>import threading from scottbrian_utils.cmds import Cmds
>>> import time
>>> def f1():
...     print('f1 entered')
...     print(cmds.get_cmd('beta'))
...     print('f1 exiting')
>>> print('mainline entered')
>>> cmds = Cmds()
>>> f1_thread = threading.Thread(target=f1)
>>> f1_thread.start()
>>> cmds.queue_cmd('beta', 'exit now')
>>> f1_thread.join()
>>> print('mainline exiting')
mainline entered
f1 entered
exit now
f1 exiting
mainline exiting


:Example: verify timing of event

>>>import threading from scottbrian_utils.cmds import Cmds
>>> import time
>>> def f1():
...     print('f1 entered')
...     cmds.start_clock(clock_iter=1)
...     cmds.get_cmd('beta')
...     assert 2 <= cmds.duration() <= 3
...     print('f1 exiting')
>>> print('mainline entered')
>>> cmds = Cmds()
>>> f1_thread = threading.Thread(target=f1)
>>> f1_thread.start()
>>> cmds.pause(2.5, clock_iter=1)
>>> cmds.queue_cmd('beta', 'exit now')
>>> f1_thread.join()
>>> print('mainline exiting')
mainline entered
f1 entered
f1 exiting
mainline exiting


The cmds module contains:

    1) Cmds class with methods:

       a. duration
       b. get_cmd
       c. pause
       d. queue_cmd
       e. start_clock

"""

########################################################################
# Standard Library
########################################################################
import queue
import threading
import time
from typing import Any, Final, Optional, Union

########################################################################
# Third Party
########################################################################

########################################################################
# Local
########################################################################

########################################################################
# type aliases
########################################################################
IntFloat = Union[int, float]
OptIntFloat = Optional[IntFloat]


########################################################################
# Cmd Exceptions classes
########################################################################
class CmdsError(Exception):
    """Base class for exception in this module."""
    pass


class GetCmdTimedOut(CmdsError):
    """Cmds get_cmd timed out waiting for cmd."""
    pass


########################################################################
# Cmd Class
########################################################################
class Cmds:
    """Cmd class for testing.

    The Cmds class is used to assist in the testing of multi-threaded
    functions. It provides a set of methods that help with test case
    coordination and verification of timed event. The test case setup
    involves a mainline thread that starts one or more remote threads.
    The queue_cmd and get_cmd methods are used for inter-thread
    communications, and the start_clock and duration methods are used to
    verify event times.

    """

    GET_CMD_TIMEOUT: Final[float] = 3.0
    CMD_Q_MAX_SIZE: Final[int] = 10

    ####################################################################
    # __init__
    ####################################################################
    def __init__(self) -> None:
        """Initialize the object."""
        # self.alpha_cmd = queue.Queue(maxsize=10)
        # self.beta_cmd = queue.Queue(maxsize=10)
        self.cmd_array: dict[str, Any] = {}
        self.cmd_lock = threading.Lock()
        self.l_msg: Any = None
        self.r_code: Any = None
        self.start_time: float = 0.0
        self.previous_start_time: float = 0.0
        self.clock_in_use = False
        self.iteration = 0

    ####################################################################
    # queue_cmd
    ####################################################################
    def queue_cmd(self, who: str, cmd: Optional[Any] = 'go') -> None:
        """Place a cmd on the cmd queue for the specified target.

        Args:
            who: arbitrary name that designates the target of the
                   command and which will be used with the get_cmd
                   method to retrieve the command
            cmd: command to place on queue

        """
        with self.cmd_lock:
            if who not in self.cmd_array:
                self.cmd_array[who] = queue.Queue(maxsize=Cmds.CMD_Q_MAX_SIZE)

        self.cmd_array[who].put(cmd,
                                block=True,
                                timeout=0.5)

    ####################################################################
    # get_cmd
    ####################################################################
    def get_cmd(self,
                who: str,
                timeout: OptIntFloat = GET_CMD_TIMEOUT) -> Any:
        """Get the next command for alpha to do.

        Args:
            who: arbitrary name that designates the target of the
                   command and which will be used with the queue_cmd
                   method to identify the intended recipient of the
                   command
            timeout: number of seconds allowed for cmd response. A
                       negative value, zero, or None means no timeout
                       will happen. If timeout is not specified, then
                       the default timeout value will be used.

        Returns:
            the cmd to perform

        Raises:
            GetCmdTimedOut: {who} timed out waiting for cmd

        """
        if timeout is None or timeout <= 0:
            timeout_value = None
        else:
            timeout_value = timeout

        with self.cmd_lock:
            if who not in self.cmd_array:
                self.cmd_array[who] = queue.Queue(maxsize=Cmds.CMD_Q_MAX_SIZE)

        start_time = time.time()
        while True:
            try:
                cmd = self.cmd_array[who].get(block=True, timeout=0.1)
                return cmd
            except queue.Empty:
                pass

            if (timeout_value
                    and timeout_value < (time.time() - start_time)):
                raise GetCmdTimedOut(f'{who} timed out waiting for cmd')

    ####################################################################
    # pause
    ####################################################################
    def pause(self,
              seconds: IntFloat,
              clock_iter: int) -> None:
        """Sleep for the number of input seconds relative to start_time.

        Args:
            seconds: number of seconds to pause
            clock_iter: clock iteration to pause on

        """
        while clock_iter != self.iteration:
            time.sleep(0.1)

        remaining_seconds = seconds - (time.time() - self.start_time)
        if remaining_seconds > 0:
            time.sleep(remaining_seconds)

    ####################################################################
    # start_clock
    ####################################################################
    def start_clock(self,
                    clock_iter: int) -> None:
        """Set the start_time to the current time.

        Args:
            clock_iter: iteration to set for the clock
        """
        while self.clock_in_use:
            time.sleep(0.1)
        self.clock_in_use = True
        self.start_time = time.time()
        self.iteration = clock_iter

    ####################################################################
    # duration
    ####################################################################
    def duration(self) -> float:
        """Return the number of seconds from the start_time.

        Returns:
            number of seconds from the start_time
        """
        ret_duration = time.time() - self.start_time
        self.clock_in_use = False
        return ret_duration
