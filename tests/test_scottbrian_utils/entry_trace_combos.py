"""entry_trace_combos.py module."""

########################################################################
# Standard Library
########################################################################
from enum import Enum, auto
import functools
import logging
import datetime
import inspect
import re
import threading
from typing import Any, cast, Optional, Union

# from ast import *
# from types import *
import ast
import types

########################################################################
# Third Party
########################################################################
import pytest

########################################################################
# Local
########################################################################
from scottbrian_utils.diag_msg import get_formatted_call_sequence
from scottbrian_utils.entry_trace import etrace
from scottbrian_utils.log_verifier import LogVer
from scottbrian_utils.log_verifier import UnmatchedExpectedMessages
from scottbrian_utils.log_verifier import UnmatchedActualMessages
from scottbrian_utils.time_hdr import get_datetime_match_string
from scottbrian_utils.entry_trace import etrace


@etrace
def f1(a):
    print(a)


f1 = functools.partial(f1, a=6)
