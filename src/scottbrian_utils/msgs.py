"""Module msgs.

====
Msgs
====

The Msgs class is intended to be used during testing to send and receive
messages between threads.

:Example: send a message to remote thread

>>> import threading from scottbrian_utils.msgs import Msgs
>>> def f1() -> None:
...     print('f1 beta entered')
...     my_msg = msgs.get_msg('beta')
...     print(my_msg)
...     print('f1 beta exiting')
>>> print('mainline entered')
>>> msgs = Msgs()
>>> f1_thread = threading.Thread(target=f1)
>>> f1_thread.start()
>>> msgs.queue_msg('beta', 'exit now')
>>> f1_thread.join()
>>> print('mainline exiting')
mainline entered
f1 beta entered
exit now
f1 beta exiting
mainline exiting


:Example: a command loop using Msgs

>>> import threading from scottbrian_utils.msgs import Msgs
>>> import time
>>> def f1() -> None:
...     print('f1 beta entered')
...     while True:
...         my_msg = msgs.get_msg('beta')
...         if my_msg == 'exit':
...             break
...         else:
...             # handle message
...             print(f'beta received msg: {my_msg}')
...             msgs.queue_msg('alpha', f'msg "{my_msg}" completed')
...     print('f1 beta exiting')
>>> print('mainline alpha entered')
>>> msgs = Msgs()
>>> f1_thread = threading.Thread(target=f1)
>>> f1_thread.start()
>>> msgs.queue_msg('beta', 'do message a')
>>> print(msgs.get_msg('alpha'))
>>> msgs.queue_msg('beta', 'do message b')
>>> print(f"alpha received response: {msgs.get_msg('alpha')}")
>>> msgs.queue_msg('beta', 'exit')
>>> f1_thread.join()
>>> print('mainline alpha exiting')
mainline alpha entered
f1 beta entered
beta received msg: do message a
alpha received response: msg "do message a" completed
beta received msg: do message b
alpha received response: msg "do message b" completed
f1 beta exiting
mainline alpha exiting


The msgs module contains:

    1) Msgs class with methods:

       a. get_msg
       b. queue_msg

"""

########################################################################
# Standard Library
########################################################################
import logging
import queue
import threading
from typing import Any, Final, Optional, Union

########################################################################
# Third Party
########################################################################
from scottbrian_utils.diag_msg import get_formatted_call_sequence
from scottbrian_utils.timer import Timer

########################################################################
# Local
########################################################################

########################################################################
# type aliases
########################################################################
IntFloat = Union[int, float]
OptIntFloat = Optional[IntFloat]


########################################################################
# Msg Exceptions classes
########################################################################
class MsgsError(Exception):
    """Base class for exception in this module."""
    pass


class GetMsgTimedOut(MsgsError):
    """Msgs get_msg timed out waiting for msg."""
    pass


########################################################################
# Msgs Class
########################################################################
class Msgs:
    """Msgs class for testing.

    The Msgs class is used to assist in the testing of multi-threaded
    functions. It provides a set of methods that help with test case
    coordination and verification. The test case setup
    involves a mainline thread that starts one or more remote threads.
    The queue_msg and get_msg methods are used for inter-thread
    communications.

    """
    GET_CMD_TIMEOUT: Final[float] = 3.0
    CMD_Q_MAX_SIZE: Final[int] = 10

    ####################################################################
    # __init__
    ####################################################################
    def __init__(self) -> None:
        """Initialize the object."""
        self.msg_array: dict[str, Any] = {}
        self.msg_lock = threading.Lock()

        # add a logger
        self.logger = logging.getLogger(__name__)

    ####################################################################
    # queue_msg
    ####################################################################
    def queue_msg(self, who: str, msg: Optional[Any] = 'go') -> None:
        """Place a msg on the msg queue for the specified target.

        Args:
            who: arbitrary name that designates the target of the
                   message and which will be used with the get_msg
                   method to retrieve the message
            msg: message to place on queue

        """
        with self.msg_lock:
            if who not in self.msg_array:
                self.msg_array[who] = queue.Queue(maxsize=Msgs.CMD_Q_MAX_SIZE)

        self.msg_array[who].put(msg,
                                block=True,
                                timeout=0.5)

    ####################################################################
    # get_msg
    ####################################################################
    def get_msg(self,
                who: str,
                timeout: OptIntFloat = GET_CMD_TIMEOUT) -> Any:
        """Get the next message for alpha to do.

        Args:
            who: arbitrary name that designates the target of the
                   message and which will be used with the queue_msg
                   method to identify the intended recipient of the
                   message
            timeout: number of seconds allowed for msg response. A
                       negative value, zero, or None means no timeout
                       will happen. If timeout is not specified, then
                       the default timeout value will be used.

        Returns:
            the received message

        Raises:
            GetMsgTimedOut: {who} timed out waiting for msg

        """
        # get a timer (the clock is started when instantiated)
        timer = Timer(timeout=timeout)

        # shared/excl lock here could improve performance
        with self.msg_lock:
            if who not in self.msg_array:
                # we need to add the message target if this is the first
                # time the target is calling get_msg
                self.msg_array[who] = queue.Queue(maxsize=Msgs.CMD_Q_MAX_SIZE)

        while True:
            try:
                msg = self.msg_array[who].get(block=True, timeout=0.1)
                return msg
            except queue.Empty:
                pass

            if timer.is_expired():
                caller_info = get_formatted_call_sequence(latest=1, depth=1)
                err_msg = (f'Thread {threading.current_thread()} '
                           f'timed out on get_msg for who: {who} '
                           f'{caller_info}')

                self.logger.debug(err_msg)
                raise GetMsgTimedOut(err_msg)
