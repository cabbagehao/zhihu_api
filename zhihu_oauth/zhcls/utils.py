# coding=utf-8

from __future__ import unicode_literals

import importlib
import functools
import os

from .urls import RE_TYPE_MAP
from ..exception import (
    IdMustBeIntException,
    MyJSONDecodeError,
    UnexpectedResponseException,
    UnimplementedException,
)

try:
    # Py3
    # noinspection PyCompatibility
    from html.parser import HTMLParser
except ImportError:
    # Py2
    # noinspection PyCompatibility,PyUnresolvedReferences
    from HTMLParser import HTMLParser

__all__ = [
    'zhihu_obj_url_parse',
    'DEFAULT_INVALID_CHARS', 'EXTRA_CHAR_FOR_FILENAME',
    'remove_invalid_char', 'add_serial_number',
    'SimpleHtmlFormatter',
    'SimpleEnum', 'ConstValue',
]

NOT_INT_ID_CLS_NAME = {'column', 'people', 'me'}

INT_ID_KEY = '_id_is_int'

"""
ID 不需要是数字的类名集合
"""


def int_id(func):
    """
    装饰器。作用于 :class:`.ZhihuClient` 中需要整型 ID 来构建对应知乎类的方法。
    作用就是个强制类型检查。

    :raise: :class:`.IdMustBeIntException` 当传过来的 ID 不是整型的时候
    """
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            some_id = args[0]
        except IndexError:
            some_id = None
        if not isinstance(some_id, int):
            raise IdMustBeIntException(self.__class__)
        setattr(self, INT_ID_KEY, True)
        return func(self, *args, **kwargs)

    return wrapper


def get_class_from_name(name, module_filename=None):
    cls_name = name.capitalize() if name.islower() else name
    file_name = module_filename or cls_name.lower()
    try:
        imported_module = importlib.import_module(
            '.' + file_name,
            'zhihu_oauth.zhcls'
        )
        return getattr(imported_module, cls_name)
    except (ImportError, AttributeError):
        raise UnimplementedException(
            'Unknown zhihu obj type [{}]'.format(name)
        )


def build_zhihu_obj_from_dict(
        data, session, use_cache=True, type_name=None,
        filename=None, cls=None, id_key='id', type_key='type'):
    obj_cls = cls or get_class_from_name(type_name or data[type_key], filename)
    obj_id = data[id_key]
    if obj_cls.__name__.lower() not in NOT_INT_ID_CLS_NAME:
        obj_id = int(obj_id)
        data.update({id_key: obj_id})
    return obj_cls(obj_id, data if use_cache else None, session)


def zhihu_obj_url_parse(url):
    for pattern, obj_type in RE_TYPE_MAP.items():
        match = pattern.match(url)
        if match:
            need_int = obj_type not in NOT_INT_ID_CLS_NAME
            obj_id = match.group(1)
            if need_int:
                obj_id = int(obj_id)
            return obj_id, obj_type
    return None, None


def can_get_from(name, data):
    return name in data and not isinstance(data[name], (dict, list))

DEFAULT_INVALID_CHARS = {':', '*', '?', '"', '<', '>', '|', '\r', '\n'}
EXTRA_CHAR_FOR_FILENAME = {'/', '\\'}


def remove_invalid_char(dirty, invalid_chars=None, for_path=False):
    if invalid_chars is None:
        invalid_chars = set(DEFAULT_INVALID_CHARS)
    else:
        invalid_chars = set(invalid_chars)
        invalid_chars.update(DEFAULT_INVALID_CHARS)
    if not for_path:
        invalid_chars.update(EXTRA_CHAR_FOR_FILENAME)

    return ''.join([c for c in dirty if c not in invalid_chars]).strip()


def add_serial_number(file_path, postfix):
    full_path = file_path + postfix
    if not os.path.isfile(full_path):
        return full_path
    num = 1
    while os.path.isfile(full_path):
        # noinspection PyUnboundLocalVariable
        try:
            # noinspection PyCompatibility,PyUnresolvedReferences
            serial = unicode(str(num))
        except NameError:
            serial = str(num)
        full_path = file_path + ' - ' + serial.rjust(3, '0') + '.' + postfix
        num += 1
    return full_path


_BASE_HTML_HEADER = """<meta name="referrer" content="no-referrer" />
<meta charset="utf-8" />
"""


class SimpleHtmlFormatter(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self._level = 0
        self._last = ''
        self._in_code = False
        self._prettified = [_BASE_HTML_HEADER]

    def handle_starttag(self, tag, attrs):
        if not self._in_code:
            self._prettified.extend(['\t'] * self._level)
        self._prettified.append('<' + tag)
        for name, value in attrs:
            self._prettified.append(' ' + name + '="' + value + '"')
        self._prettified.append('>')
        if not self._in_code:
            self._prettified.append('\n')
        if tag != 'br' and tag != 'img':
            self._level += 1
        if tag == 'code':
            self._in_code = True
        self._last = tag

    def handle_endtag(self, tag):
        if tag != 'br' and tag != 'img':
            self._level -= 1
        if not self._in_code:
            self._prettified.extend(['\t'] * self._level)
        self._prettified.append('</' + tag + '>')
        if not self._in_code:
            self._prettified.append('\n')
        self._last = tag
        if tag == 'code':
            self._in_code = False

    def handle_startendtag(self, tag, attrs):
        if not self._in_code:
            self._prettified.extend(['\t'] * self._level)
        self._prettified.append('<' + tag)
        for name, value in attrs:
            self._prettified.append(' ' + name + '="' + value + '"')
        self._prettified.append('/>')
        self._last = tag

    def handle_data(self, data):
        if not self._in_code:
            self._prettified.extend(['\t'] * self._level)
            if self._last == 'img':
                self._prettified.append('<br>\n')
                self._prettified.extend(['\t'] * self._level)
        self._prettified.append(data)
        if not self._in_code:
            self._prettified.append('\n')

    def handle_charref(self, name):
        self._prettified.append('&#' + name)

    def handle_entityref(self, name):
        self._prettified.append('&' + name + ';')

    def error(self, message):
        self._prettified = ['error when parser the html file.']

    def prettify(self):
        return ''.join(self._prettified)


class SimpleEnum(set):
    def __getattr__(self, item):
        if item in self:
            return item
        raise AttributeError('No {0} in this enum class.'.format(item))


class ConstValue(object):
    def __init__(self, value=None):
        self._value = value

    def __get__(self, instance, cls):
        return self._value

    def __set__(self, instance, value):
        raise TypeError('Can\'t change value of a const var')


def get_result_or_error(url, res):
    try:
        json_dict = res.json()
        if 'error' in json_dict:
            return False, json_dict['error']['message']
        elif 'success' in json_dict:
            if json_dict['success']:
                return True, ''
            else:
                return False, 'Unknown error'
        else:
            return True, ''
    except (KeyError, MyJSONDecodeError):
        raise UnexpectedResponseException(
            url, res, 'a json contains voting result or error message')


def common_save(path, filename, content, default_filename, invalid_chars):
    filename = filename or default_filename
    filename = remove_invalid_char(filename, invalid_chars)
    filename = filename or 'untitled'

    path = path or '.'
    path = remove_invalid_char(path, invalid_chars, True)
    path = path or '.'

    if not os.path.isdir(path):
        os.makedirs(path)
    full_path = os.path.join(path, filename)
    full_path = add_serial_number(full_path, '.html')
    formatter = SimpleHtmlFormatter()
    formatter.feed(content)
    with open(full_path, 'wb') as f:
        f.write(formatter.prettify().encode('utf-8'))
