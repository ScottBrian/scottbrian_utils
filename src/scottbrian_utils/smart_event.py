"""Module smart_event.

=============
SmartEvent
=============

You can use the SmartEvent class to coordinate activities between two
or more threads with the added feature of being able to recognize
when a thread has ended. This helps solves a problem where either:

  1) a mainline application waits forever on an event that will never be set
     because the thread that was supposed to set it has ended with an
     exception.
  2) a thread started by mainline waits forever on an event that will never be
     set because mainline, which was supposed to set it, has ended with an
     exception.


:Example: create a SmartEvent for mainline and a thread to use

>>> from scottbrian_utils.smart_event import SmartEvent
>>> import threading
>>> import time
>>> smart_event = SmartEvent()
>>> def f1(in_smart_event):
...     try:
...         time.sleep(3)
...         in_smart_event.set()
...     except SmartEventMainlineNotAlive as e:
...         print('mainline is not alive')
>>> f1_thread = threading.Thread(target=f1, args=(smart_event,)
>>> f1_thread.start()
>>> try:
>>>     smart_event.wait()
>>>     smart_event.clear()
>>> except SmartEventThreadNotAlive:
>>>     print('Thread is not alive')


The smart_event module contains:

    1) SmartEvent class with methods:

       a. wait
       b. set
       c. clear

"""
import time
import threading
import queue
from typing import (Any, Final, Optional, Type, TYPE_CHECKING, Union)

# from scottbrian_utils.diag_msg import diag_msg

import logging

logger = logging.getLogger(__name__)
logging.getLogger(__name__).addHandler(logging.NullHandler())


###############################################################################
# SmartEvent class exceptions
###############################################################################
class SmartEventError(Exception):
    """Base class for exceptions in this module."""
    pass


class SmartEventMainlineNotAlive(SmartEventError):
    """SmartEvent mainline is not alive."""
    pass


class SmartEventThreadNotAlive(SmartEventError):
    """SmartEvent thread not alive."""
    pass


###############################################################################
# SmartEvent class
###############################################################################
class SmartEvent(threading.Event):
    """SmartEvent class."""

    def __init__(self,
                 thread_object: threading.Thread):
        """Initialize SmartEvent object.

        Args:
            thread_object: the thread object that mainline will
        """
        super().__init__()
        self.thread_object = thread_object

    def wait(self, timeout=None):
        if timeout:
            t_out = min(0.1, timeout)
        else:
            t_out = 0.1
        start_time = time.time()
        while not super().wait(timeout=t_out):
            if threading.current_thread() is threading.main_thread():
                if not self.thread_object.is_alive():
                    raise Exception('mainline wait sees thread is gone')
            elif not threading.main_thread().is_alive():
                raise Exception('thread wait sees mainline is gone')
            if timeout and (timeout <= (time.time() - start_time)):
                return False
        return True

    def set(self):
        super().set()
        if threading.current_thread() is threading.main_thread():
            if not self.thread_object.is_alive():
                raise Exception('mainline set sees thread is gone')
        elif not threading.main_thread().is_alive():
            raise Exception('thread set sees mainline is gone')

    # def set_exc(self, exc):
    #     self.exc = exc

class SmartEvent:
    """Provides a communication link between threads."""

    MAX_MSGS_DEFAULT: Final[int] = 16

    def __init__(self,
                 max_msgs: Optional[int] = None
                 ) -> None:
        """Initialize an instance of the SmartEvent class.

        Args:
            max_msgs: Number of messages that can be placed onto the send
                        queue until being received. Once the max has
                        been reached, no more sends will be allowed
                        until messages are received from the queue. The
                        default is 16
        """
        if max_msgs:
            self.max_msgs = max_msgs
        else:
            self.max_msgs = SmartEvent.MAX_MSGS_DEFAULT
        self.main_send = queue.Queue(maxsize=self.max_msgs)
        self.main_recv = queue.Queue(maxsize=self.max_msgs)

        self.main_thread_id = threading.get_ident()
        self.child_thread_id: Any = 0
        logger.info(f'SmartEvent created by thread ID {self.main_thread_id}')

    ###########################################################################
    # repr
    ###########################################################################
    def __repr__(self) -> str:
        """Return a representation of the class.

        Returns:
            The representation as how the class is instantiated

        :Example: instantiate an SmartEvent

        >>> from scottbrian_utils.smart_event import SmartEvent
        >>> smart_event = SmartEvent()
        >>> repr(smart_event)
        SmartEvent(max_msgs=16)

        """
        if TYPE_CHECKING:
            __class__: Type[SmartEvent]
        classname = self.__class__.__name__
        parms = f'max_msgs={self.max_msgs}'

        return f'{classname}({parms})'

    ###########################################################################
    # set_child_thread_id
    ###########################################################################
    def set_child_thread_id(self,
                            child_thread_id: Optional[Any] = None
                            ) -> None:
        """Set child thread id.

        Args:
            child_thread_id: the id to set. The default is None which will set
                               the id to the caller's thread id

        :Example: instantiate a SmartEvent and set the id to 5

        >>> from scottbrian_utils.smart_event import SmartEvent
        >>> smart_event = SmartEvent()
        >>> smart_event.set_child_thread_id(5)
        >>> print(smart_event.get_child_thread_id())
        5
        """
        if child_thread_id:
            self.child_thread_id = child_thread_id
        else:
            self.child_thread_id = threading.get_ident()

    ###########################################################################
    # get_child_thread_id
    ###########################################################################
    def get_child_thread_id(self) -> Any:
        """Get child thread id.

        Returns:
            child thread id

        :Example: instantiate a SmartEvent and set the id to 5

        >>> from scottbrian_utils.smart_event import SmartEvent
        >>> smart_event = SmartEvent()
        >>> smart_event.set_child_thread_id('child_A')
        >>> print(smart_event.get_child_thread_id())
        child_A

        """
        return self.child_thread_id

    ###########################################################################
    # send
    ###########################################################################
    def send(self,
             msg: Any,
             timeout: Optional[Union[int, float]] = None) -> None:
        """Send a msg.

        Args:
            msg: the msg to be sent
            timeout: number of seconds to wait for full queue to get free slot

        Raises:
            SmartEventSendFailed: send method unable to send the
                                    message because the send queue
                                    is full with the maximum
                                    number of messages.

        :Example: instantiate a SmartEvent and send a message

        >>> from scottbrian_utils.smart_event import SmartEvent
        >>> import threading
        >>> def f1(smart_event: SmartEvent) -> None:
        ...     msg = smart_event.recv()
        ...     if msg == 'hello thread':
        ...         smart_event.send('hi')
        >>> a_smart_event = SmartEvent()
        >>> thread = threading.Thread(target=f1, args=(a_smart_event,))
        >>> thread.start()
        >>> a_smart_event.send('hello thread')
        >>> print(a_smart_event.recv())
        hi

        >>> thread.join()

        """
        try:
            if self.main_thread_id == threading.get_ident():  # if main
                logger.info(f'SmartEvent main {self.main_thread_id} sending '
                            f'msg to child {self.child_thread_id}')
                self.main_send.put(msg, timeout=timeout)  # send to child
            else:  # else not main
                logger.info(f'SmartEvent child {self.child_thread_id} '
                            f'sending msg to main {self.main_thread_id}')
                self.main_recv.put(msg, timeout=timeout)  # send to main
        except queue.Full:
            logger.error('Raise SmartEventSendFailed')
            raise SmartEventSendFailed('send method unable to send the '
                                       'message because the send queue '
                                       'is full with the maximum '
                                       'number of messages.')

    ###########################################################################
    # recv
    ###########################################################################
    def recv(self, timeout: Optional[Union[int, float]] = None) -> Any:
        """Send a msg.

        Args:
            timeout: number of seconds to wait for message

        Returns:
            message unless timeout occurs

        Raises:
            SmartEventRecvTimedOut: recv processing timed out
                                      waiting for a message to
                                      arrive.

        """
        try:
            if self.main_thread_id == threading.get_ident():  # if main
                logger.info(f'SmartEvent main {self.main_thread_id} receiving '
                            f'msg from child {self.child_thread_id}')
                return self.main_recv.get(timeout=timeout)  # recv from child
            else:  # else child
                logger.info(f'SmartEvent child {self.child_thread_id} '
                            f'receiving msg from main {self.main_thread_id}')
                return self.main_send.get(timeout=timeout)  # recv from main
        except queue.Empty:
            logger.error('Raise SmartEventRecvTimedOut')
            raise SmartEventRecvTimedOut('recv processing timed out '
                                         'waiting for a message to '
                                         'arrive.')

    ###########################################################################
    # send_recv
    ###########################################################################
    def send_recv(self,
                  msg: Any,
                  timeout: Optional[Union[int, float]] = None) -> Any:
        """Send a message and wait for reply.

        Args:
            msg: the msg to be sent
            timeout: Number of seconds to wait for reply

        Returns:
              message unless send q is full or timeout occurs during recv

        :Example: instantiate a SmartEvent and send a message

        >>> from scottbrian_utils.smart_event import SmartEvent
        >>> import threading
        >>> def f1(smart_event: SmartEvent) -> None:
        ...     msg = smart_event.recv()
        ...     if msg == 'hello thread':
        ...         smart_event.send('hi')
        >>> a_smart_event = SmartEvent()
        >>> thread = threading.Thread(target=f1, args=(a_smart_event,))
        >>> thread.start()
        >>> a_smart_event.send('hello thread')
        >>> print(a_smart_event.recv())
        hi

        >>> thread.join()

        """
        self.send(msg, timeout=timeout)
        return self.recv(timeout=timeout)

    ###########################################################################
    # msg_waiting
    ###########################################################################
    def msg_waiting(self) -> bool:
        """Determine whether a message is waiting, ready to be received.

        Returns:
            True if message is ready to receive, False otherwise

        :Example: instantiate a SmartEvent and set the id to 5

        >>> from scottbrian_utils.smart_event import SmartEvent
        >>> class SmartEventApp(threading.Thread):
        ...     def __init__(self,
        ...                  smart_event: SmartEvent,
        ...                  event: threading.Event) -> None:
        ...         super().__init__()
        ...         self.smart_event = smart_event
        ...         self.event = event
        ...         self.smart_event.set_child_thread_id()
        ...     def run(self) -> None:
        ...         self.smart_event.send('goodbye')
        ...         self.event.set()
        >>> smart_event = SmartEvent()
        >>> event = threading.Event()
        >>> smart_event_app = SmartEventApp(smart_event, event)
        >>> print(smart_event.msg_waiting())
        False

        >>> smart_event_app.start()
        >>> event.wait()
        >>> print(smart_event.msg_waiting())
        True

        >>> print(smart_event.recv())
        goodbye

        """
        if self.main_thread_id == threading.get_ident():
            return not self.main_recv.empty()
        else:
            return not self.main_send.empty()
