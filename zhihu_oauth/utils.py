# coding=utf-8

from __future__ import unicode_literals

import functools

from .exception import NeedLoginException

__all__ = ['need_login']


def need_login(func):
    """
    装饰器。作用于 :class:`.ZhihuClient` 中的某些方法，
    强制它们必须在登录状态下才能被使用。
    """
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        if self.is_login():
            return func(self, *args, **kwargs)
        else:
            raise NeedLoginException(func.__name__)

    return wrapper
