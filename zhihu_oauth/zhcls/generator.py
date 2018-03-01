# coding=utf-8

from __future__ import unicode_literals

import abc
import functools
import sys
import warnings

from .utils import build_zhihu_obj_from_dict
from ..exception import GetEmptyResponseWhenFetchData, MyJSONDecodeError, \
    TokenError, UnexpectedResponseException, UnimplementedException, \
    UnimplementedWarning

__all__ = [
    'BaseGenerator', 'FilterableGenerator',
    'ActivityGenerator', 'AnswerGenerator', 'ArticleGenerator',
    'CollectionContentGenerator', 'CollectionGenerator',
    'ColumnGenerator', 'CommentGenerator',
    'FeedGenerator',
    'LiveGenerator', 'LiveOfTagGenerator',
    'MessageGenerator',
    'PeopleGenerator', 'PeopleWithLiveBadgeGenerator', 'PinGenerator',
    'QuestionGenerator',
    'SearchResultGenerator',
    'TopicGenerator',
    'WhisperGenerator',
]


class BaseGenerator(object):
    def __init__(self, url, session, **default_params):
        """
        基础生成器类。

        :param url: 首次请求网址。后续网址在 API 的返回数据中会给出。
        :param session: 网络会话。
        :param default_params: 需要加到每次请求中的 get query params
        """
        self._url = url
        self._session = session
        self._index = 0
        self._data = []
        self._up = 0
        self._next_url = self._url
        self._need_sleep = 0.5
        self._default_params = dict(default_params if default_params else {})
        self._extra_params = {}

    def _fetch_more(self):
        """
        获取下一页数据。

        内部流程：

        1. 从 self._extra_params 中获取附加请求参数，并发送请求。
        2. 将响应解析成 JSON，如果出错则抛出异常。
        3. 如果 JSON 数据未出错（没有名为 ``error`` 的键），则转 4。

           - 如果错误名是 'ERR_CONVERSATION_NOT_FOUND' 则转 7（其实这是个 dirty hack，
             因为有些评论没有对话列表，而我有没有找到判断方法。）
           - 将等待时间翻倍，若其值超过最长等待时间限制，转 7。
             否则 sleep 当前值然后返回。
             （因为这里没有改变下一页所以下次会继续请求统一页面）

        4. 将等待时间重置为 0.5 s。
        5. 将数据添加到对象内部数据库中。
        6. 如果数据表示未达到末尾，则根据数据设置下一次请求地址，返回。
        7. 将下一次请求网址设为 None，这表示所有数据均取完，返回。

        :raise: :any:`UnexpectedResponseException`
        """
        params = dict(self._default_params)
        params.update(self._extra_params)

        # `offset` params only used in first request
        if self._next_url != self._url and 'offset' in params:
            del params['offset']

        res = self._session.get(self._next_url, params=params)
        try:
            json_dict = res.json()

            # Empty data({}, []) as end
            if not json_dict:
                warnings.warn(GetEmptyResponseWhenFetchData)
                self._next_url = None
                return

            # Server knows error happened
            if 'error' in json_dict:

                error = json_dict['error']

                # comment conversion hack, as end
                if 'name' in error:
                    if error['name'] == 'ERR_CONVERSATION_NOT_FOUND':
                        self._next_url = None
                        return

                # token error
                if 'code' in error:
                    if error['code'] == 100:
                        raise TokenError(error['message'])

                # other error
                raise UnexpectedResponseException(
                    self._next_url,
                    res,
                    "a json string, has data and paging"
                )

            self._up += len(json_dict['data'])
            self._data.extend(json_dict['data'])
            if json_dict['paging']['is_end']:
                self._next_url = None
            else:
                self._next_url = json_dict['paging']['next']
        except (MyJSONDecodeError, AttributeError):
            raise UnexpectedResponseException(
                self._next_url,
                res,
                'a json string, has data and paging'
            )

    @abc.abstractmethod
    def _build_obj(self, data):
        """
        这是个抽象方法，子类需要自己实现创建对象并返回的操作。

        子类的操作很简单，下文文档中就不详细写了。

        :param data: 提供的数据，为返回的 JSON 数据的 data 列表中的一个 dict。
        :return: 构建出的对象。
        """
        return None

    def __getitem__(self, item):
        """
        重载自身的 ``[int]`` 操作符。逻辑如下：

        1. 如果要求的 index 小于现在对象内部数据库中对象数量，
           从数据库中数据，使用 _build_obj 出构建对象并返回。
        2. 如果下一页地址不为 None，则调用 :any:`_fetch_more` 请求更多数据。
           否则抛出 IndexError 异常表示超出范围。
        3. 因为请求过程中更新了数据库，再转 1。

        结合 :any:`_fetch_more` 能更好地理解本函数。

        :param int item: 索引，必须为整型。
        :return: 对应的对象。
        :raise IndexError: 请求完全部数据后，索引还是大于数据库内数据量。
        """
        if not isinstance(item, int):
            raise TypeError('Need an int as index, not {0}'.format(type(item)))
        if item < 0:
            raise ValueError('index must >= 0, {} provided'.format(item))

        while item >= self._up:
            if self._next_url is not None:
                self._fetch_more()
            else:
                raise IndexError('list index out of range')
        return self._build_obj(self._data[item])

    def __iter__(self):
        self._reset()
        return self

    def __next__(self):
        """
        提供迭代方式访问数据集，即 ``for xx in obj.xxxs`` 。

        对象内有一个变量 ``_index`` 保存着下一次要迭代的下标。

        每次用户迭代时，使用被 :any:`__getitem__ <BaseGenerator.__getitem__>`
        方法重写过的 self[self._index] 操作符尝试获取对象。

        如果引发了 ``IndexError`` 则表示数据获取完毕。此时提供一个
         ``StopIteration`` 结束迭代，并把 ``_index`` 变量置为 0 为下次迭代做准备。

        如果成功获取到数据则把 ``_index + 1``，然后返回对象。

        结合 :any:`__getitem__ <BaseGenerator.__getitem__>` 能更好地理解本函数。
        """
        obj = None
        while obj is None:
            try:
                obj = self[self._index]
            except IndexError:
                self._index = 0
                raise StopIteration
            self._index += 1
        return obj

    next = __next__

    def order_by(self, what):
        """
        有些 API 可以根据 GET 参数来控制数据的排序，只需流式的调用本函数即可。

        目前发现支持的使用方式只有：

        - ``People.answers.order_by('votenum')``，
          表示按赞数排序获取某人答案。默认为按时间。
          （由于 Me 类继承于 People，所以 ``me.answers``）也可以。

        如果我发现了其他方式会更新文档。

        ..  warning:: 注意

            使用这一函数会重置对象内部的所有数据，
            再次取数据将从头开始。

        其实就是个 :any:`add_params` 的封装……

        :param str|unicode what: 按什么排序……
        """
        return self.add_params(order_by=what)

    def jump(self, n):
        """
        忽略前 n 个数据，直接去获取第 n+1 个数据

        :param int n: 跳过多少数据
        """
        return self.add_params(offset=int(n))

    def _reset(self):
        """
        重置数据。
        """
        del self._data[:]
        self._index = 0
        self._up = 0
        self._next_url = self._url
        self._need_sleep = 0.5

    def set_params(self, *_, **params):
        """
        自定义请求时的 params，如果不了解知乎 OAuth API 的话并没有什么用。

        ..  warning:: 注意

            使用这一函数会重置对象内部的所有数据，
            再次取数据将从头开始。

        使用方式：``for xxx in obj.xxxs.set_params(a='b', c='d'):``
        """
        self._extra_params.clear()
        return self.add_params(**params)

    def add_params(self, *_, **params):
        """
        添加请求时的 params，如果不了解知乎 OAuth API 的话并没有什么用。

        ..  note:: 注意

            使用这一函数会重置对象内部的除了额外 params 外的数据，
            再次取数据将从头开始。

        使用方式：``for xxx in obj.xxxs.add_params(a='b').add_params(b='b'):``
        """
        self._reset()
        self._extra_params.update(params)
        return self


class FilterableGenerator(BaseGenerator):
    def __init__(self, url, session, filter_set, obj_cls, **kwargs):
        self._condition = None
        self._condition_is_func = False
        self._filter_set = filter_set
        self._obj_cls = obj_cls
        super(FilterableGenerator, self).__init__(url, session, **kwargs)

    def filter(self, cond):
        self._condition_is_func = False
        if isinstance(cond, str) and cond in self._filter_set:
            cond = {cond}
        elif isinstance(cond, set) \
                and all([x in self._filter_set for x in cond]):
            pass
        elif hasattr(cond, '__call__'):
            self._condition_is_func = True
        else:
            raise ValueError('Argument cond can only be '
                             'XxxType.xxx, or a set of theme, '
                             'or a callable like func(obj) -> Bool.')

        self._condition = cond

        return self

    def _build_obj(self, data):
        try:
            obj = self._obj_cls(data, self._session)
        except UnimplementedException as e:
            warnings.warn(UnimplementedWarning(e))
            return None
        if self._condition is not None:
            if self._condition_is_func:
                if not self._condition(obj):
                    return None
            elif obj.type not in self._condition:
                return None
        return obj


class ActivityGenerator(FilterableGenerator):
    def __init__(self, url, session, **kwargs):
        from .activity import Activity, ActType
        super(ActivityGenerator, self).__init__(
            url, session, ActType, Activity, **kwargs
        )

    def filter(self, cond):
        """
        设置想要获取哪个或哪些类型的动态。例子：

        ..  code-block:: python

            xxx = client.people('xxx')

            for act in xxx.activities.filter(ActType.VOTEUP_ANSWER):
                print(ts2str(act.created_time), act2str(act))

        参数也可以是多个 :any:`ActType` 的 set：

        ..  code-block:: python

            xxx = client.people('xxx')

            filter_types = {
                ActType.VOTEUP_ANSWER,
                ActType.VOTEUP_ARTICLE,
                ActType.FOLLOW_QUESTION,
            }

            for act in xxx.activities.filter(filter_types):
                print(ts2str(act.created_time), act2str(act))

        参数还可以是一个接收 :any:`Activity` 对象，返回值为 Bool 的函数：

        ..  code-block:: python

            xxx = client.people('xxx')

            for act in xxx.activities.filter(lambda x: '游戏' in act2str(x)):
                print(ts2str(act.created_time), act2str(act))

        ..  warning:: 需要注意的是，使用 filter 并不会减少网络请求，使程序变快

            因为知乎官方并没有提供根据动态类型获取动态的接口，
            所以内部实现其实依旧获取了用户的所有动态，只是在生成器返回数据时进行了过滤。

        :param ActType|{ActType}|callable cond: 过滤条件
        """
        return super(ActivityGenerator, self).filter(cond)


class AnswerGenerator(BaseGenerator):
    def __init__(self, url, session):
        super(AnswerGenerator, self).__init__(url, session)

    def _build_obj(self, data):
        from .answer import Answer
        return build_zhihu_obj_from_dict(
            data, self._session, cls=Answer
        )


class ArticleGenerator(BaseGenerator):
    def __init__(self, url, session):
        super(ArticleGenerator, self).__init__(url, session)

    def _build_obj(self, data):
        from .article import Article
        return build_zhihu_obj_from_dict(
            data, self._session, cls=Article
        )


class CollectionContentGenerator(BaseGenerator):
    def __init__(self, url, session):
        super(CollectionContentGenerator, self).__init__(url, session)

    def _build_obj(self, data):
        if data['type'] in {'answer', 'article'}:
            return build_zhihu_obj_from_dict(data, self._session)
        else:
            raise UnimplementedException(
                'Unknown collection content type: {0}. '
                'Please send this error message to '
                'developer to get help.'.format(data['type'])
            )


class CollectionGenerator(BaseGenerator):
    def __init__(self, url, session):
        super(CollectionGenerator, self).__init__(url, session)

    def _build_obj(self, data):
        from .collection import Collection
        return build_zhihu_obj_from_dict(
            data, self._session, cls=Collection
        )


class ColumnGenerator(BaseGenerator):
    def __init__(self, url, session):
        super(ColumnGenerator, self).__init__(url, session)

    def _build_obj(self, data):
        from .column import Column
        return build_zhihu_obj_from_dict(
            data, self._session, cls=Column
        )


class CommentGenerator(BaseGenerator):
    def __init__(self, url, session):
        super(CommentGenerator, self).__init__(url, session)

    def _build_obj(self, data):
        from .comment import Comment
        return build_zhihu_obj_from_dict(
            data, self._session, cls=Comment
        )


class FeedGenerator(FilterableGenerator):
    def __init__(self, url, session, **kwargs):
        from .feed import Feed, FeedType
        super(FeedGenerator, self).__init__(
            url, session, FeedType, Feed, **kwargs
        )

    def filter(self, cond):
        """
        参见 :any:`ActivityGenerator.filter` 函数，使用方式基本相同

        例子见 :any:`Feed`
        """
        return super(FeedGenerator, self).filter(cond)


class LiveGenerator(BaseGenerator):
    def __init__(self, url, session, **kwargs):
        super(LiveGenerator, self).__init__(url, session, **kwargs)

    def _build_obj(self, data):
        from .live import Live
        return build_zhihu_obj_from_dict(
            data, self._session, cls=Live
        )


class LiveOfTagGenerator(LiveGenerator):
    def __init__(self, url, session, **kwargs):
        super(LiveOfTagGenerator, self).__init__(url, session, **kwargs)


class MessageGenerator(BaseGenerator):
    def __init__(self, url, session, **kwargs):
        super(MessageGenerator, self).__init__(url, session, **kwargs)

    def _build_obj(self, data):
        from .message import Message
        return build_zhihu_obj_from_dict(
            data, self._session, cls=Message
        )


class PeopleGenerator(BaseGenerator):
    def __init__(self, url, session):
        super(PeopleGenerator, self).__init__(url, session)

    def _build_obj(self, data):
        from .people import People

        # hack for topic.best_answerers
        if data['type'] == 'best_answerers':
            data = data['member']

        return build_zhihu_obj_from_dict(
            data, self._session, cls=People
        )


class PeopleWithLiveBadgeGenerator(BaseGenerator):
    def __init__(self, url, session):
        super(PeopleWithLiveBadgeGenerator, self).__init__(url, session)

    def _build_obj(self, data):
        from .people import People
        from .live import LiveBadge

        return (
            data['role'],
            build_zhihu_obj_from_dict(
                data['badge'], self._session, cls=LiveBadge,
            ),
            build_zhihu_obj_from_dict(
                data['member'], self._session, cls=People,
            ),
        )


class PinGenerator(BaseGenerator):
    def __init__(self, url, session):
        super(PinGenerator, self).__init__(url, session)

    def _build_obj(self, data):
        from .pin import Pin
        return build_zhihu_obj_from_dict(
            data, self._session, cls=Pin
        )


class QuestionGenerator(BaseGenerator):
    def __init__(self, url, session):
        super(QuestionGenerator, self).__init__(url, session)

    def _build_obj(self, data):
        from .question import Question
        return build_zhihu_obj_from_dict(
            data, self._session, cls=Question
        )


class SearchResultGenerator(BaseGenerator):
    def __init__(self, url, session, **kwargs):
        super(SearchResultGenerator, self).__init__(url, session, **kwargs)

    def _build_obj(self, data):
        from .search import data_to_section_or_result, SearchResult
        res = data_to_section_or_result(data, self._session)

        # Bypass Zhihu AD result in search results
        if isinstance(res, SearchResult):
            try:
                _ = res.obj
            except UnimplementedException as e:
                if '[promotion]' in str(e):
                    return None
                raise e

        return res


class TopicGenerator(BaseGenerator):
    def __init__(self, url, session):
        super(TopicGenerator, self).__init__(url, session)

    def _build_obj(self, data):
        from .topic import Topic
        return build_zhihu_obj_from_dict(
            data, self._session, cls=Topic
        )


class TopicActivityGenerator(BaseGenerator):
    def __init__(self, url, session):
        super(TopicActivityGenerator, self).__init__(url, session)

    def _build_obj(self, data):
        answer_list = data.get('answers', [])
        answer_count = len(answer_list)
        if answer_count == 0:
            # Only question
            return build_zhihu_obj_from_dict(data, self._session)
        elif answer_count == 1:
            return build_zhihu_obj_from_dict(answer_list[0], self._session)
        else:
            raise UnimplementedWarning(UnimplementedException(
                'I think question generated by Topic.activities has only '
                'one answer at most, if you see this warning, '
                'which proves that I am wrong, '
                'please open a issue in Github with the data ' + str(data)
            ))
            return None


class WhisperGenerator(BaseGenerator):
    def __init__(self, url, session):
        super(WhisperGenerator, self).__init__(url, session)

    def _build_obj(self, data):
        from .whisper import Whisper
        return build_zhihu_obj_from_dict(
            data, self._session, cls=Whisper
        )


def generator_of(url_pattern, class_name=None, format_id=True, **params):
    def wrappers_wrapper(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            from .people import People

            cls_name = class_name or func.__name__

            if cls_name.endswith('s'):
                cls_name = cls_name[:-1]

            if cls_name.islower():
                cls_name = cls_name.capitalize()

            gen_cls_name = cls_name + 'Generator'
            try:
                gen_cls = getattr(sys.modules[__name__], gen_cls_name)
            except AttributeError:
                return func(self, *args, **kwargs)

            if isinstance(self, People):
                self._get_data()

            default_params = params
            if gen_cls is MessageGenerator:
                # self is whisper object,
                # who attr is people object, for who i'm talking to
                default_params['sender_id'] = self.who.id
            elif gen_cls is ActivityGenerator:
                # 获取用户动态需要加上 action_feed=true
                # 如果不加某些用户动态获取中途会出错
                default_params['action_feed'] = 'true'
            elif gen_cls is LiveOfTagGenerator:
                default_params['tags'] = self.id

            if format_id:
                url = url_pattern.format(self.id)
            else:
                url = url_pattern

            return gen_cls(url, self._session, **default_params)

        return wrapper

    return wrappers_wrapper
