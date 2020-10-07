#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jun 12 15:47:20 2020

@author: Scott Tuttle
"""

from typing import Any, Callable, NewType, Optional, TextIO, TypeVar, Union
from typing import overload

def decorator(wrapper: Optional[Callable[..., Any]] = None,
              enabled: Any = None,
              adapter: Any = None) -> Callable[..., Any]: ...

F = TypeVar('F', bound=Callable[..., Any])
DT_Format = NewType('DT_Format', str)
default_dt_format: DT_Format = DT_Format('%a %b %d %Y %H:%M:%S')
@overload
def time_box(wrapped: F, *,
             # dt_format: DT_Format = StartStopHeader.default_dt_format,
             dt_format: DT_Format = default_dt_format,
             end: str = '\n',
             file: Optional[TextIO] = None,
             flush: bool = False,
             time_box_enabled: Union[bool, Callable[..., bool]] = True
             ) -> F: ...


@overload
def time_box(*,
             # dt_format: DT_Format = StartStopHeader.default_dt_format,
             dt_format: DT_Format = default_dt_format,
             end: str = '\n',
             file: Optional[TextIO] = None,
             flush: bool = False,
             time_box_enabled: Union[bool, Callable[..., bool]] = True
             ) -> Callable[[F], F]: ...

