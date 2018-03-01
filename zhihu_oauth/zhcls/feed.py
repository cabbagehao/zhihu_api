# coding=utf-8

from __future__ import unicode_literals

from itertools import chain

from .streaming import StreamingJSON
from .utils import SimpleEnum, build_zhihu_obj_from_dict
from ..exception import UnimplementedException

__all__ = ['Feed', 'FeedType']

_VERB_TO_FEED_TYPE_MAP = {
    'COLUMN_POPULAR_ARTICLE': 'COLUMN_POPULAR_ARTICLE',
    'LIVE_JOIN': 'JOIN_LIVE',
    'MEMBER_ANSWER_QUESTION': 'CREATE_ANSWER',
    'MEMBER_ASK_QUESTION': 'CREATE_QUESTION',
    'MEMBER_COLLECT_ANSWER': 'COLLECT_ANSWER',
    'MEMBER_COLLECT_ARTICLE': 'COLLECT_ARTICLE',
    'MEMBER_CREATE_ARTICLE': 'CREATE_ARTICLE',
    'MEMBER_CREATE_PIN': 'CREATE_PIN',
    'MEMBER_FOLLOW_COLLECTION': 'FOLLOW_COLLECTION',
    'MEMBER_FOLLOW_COLUMN': 'FOLLOW_COLUMN',
    'MEMBER_FOLLOW_QUESTION': 'FOLLOW_QUESTION',
    'MEMBER_FOLLOW_ROUNDTABLE': 'FOLLOW_ROUNDTABLE',
    'MEMBER_FOLLOW_TOPIC': 'FOLLOW_TOPIC',
    'MEMBER_LIKE_PIN': 'LIKE_PIN',
    'MEMBER_VOTEUP_ANSWER': 'VOTEUP_ANSWER',
    'MEMBER_VOTEUP_ARTICLE': 'VOTEUP_ARTICLE',
    'MEMBER_VOTEUP_EBOOK': 'VOTEUP_EBOOK',
    'TOPIC_ACKNOWLEDGED_ANSWER': 'ANSWER_FROM_TOPIC',
    'TOPIC_ACKNOWLEDGED_ARTICLE': 'ARTICLE_FROM_TOPIC',
    'TOPIC_ACKNOWLEDGED_EBOOK': 'EBOOK_FROM_TOPIC',
    'TOPIC_POPULAR_QUESTION': 'QUESTION_FROM_TOPIC',
}

_TYPE_TO_FEED_TYPE_MAP = {
    'action_card': 'CARD',
    'feed_advert': 'AD',
}

FeedType = SimpleEnum(
    chain(_VERB_TO_FEED_TYPE_MAP.values(), _TYPE_TO_FEED_TYPE_MAP.values())
)
"""
FeedType 是用于表示首页信息流单个 Feed 类型的枚举类，可供使用的常量有：

====================== ================== ======================
常量名                  说明               `target` 属性类型
====================== ================== ======================
COLLECT_ANSWER          收藏答案            :any:`Answer`
COLLECT_ARTICLE         收藏文章            :any:`Article`
COLUMN_POPULAR_ARTICLE  热门专栏文章        :any:`Article`
CREATE_ANSWER           回答问题            :any:`Answer`
CREATE_ARTICLE          发表文章            :any:`Article`
CREATE_PIN              发表分享            :any:`Pin`
CREATE_QUESTION         提出问题            :any:`Question`
FOLLOW_COLLECTION       关注收藏夹          :any:`Collection`
FOLLOW_COLUMN           关注专栏            :any:`Column`
FOLLOW_QUESTION         关注问题            :any:`Question`
FOLLOW_ROUNDTABLE       关注圆桌            :any:`StreamingJSON`
FOLLOW_TOPIC            关注话题            :any:`Topic`
LIKE_PIN                赞了分享            :any:`Pin`
VOTEUP_ANSWER           赞同回答            :any:`Answer`
VOTEUP_ARTICLE          赞同文章            :any:`Article`
VOTEUP_EBOOK            赞了电子书          :any:`StreamingJSON`
ANSWER_FROM_TOPIC       来自话题的答案      :any:`Answer`
ARTICLE_FROM_TOPIC      来自话题的文章      :any:`Article`
EBOOK_FROM_TOPIC        来自话题的电子书    :any:`StreamingJSON`
QUESTION_FROM_TOPIC     来自话题的问题      :any:`Question`
ACTION_CARD             卡片式广告          ``None``
AD                      简单广告            ``None``
====================== ================== ======================

上述 ``ACTION_CARD`` 型 Feed 的内容请参见 :any:`Feed.promotions`；``AD``
型 Feed 内容参见 :any:`Feed.ad`。

"""

_NON_TRIVIAL_FEED_TYPES = {FeedType.CARD, FeedType.AD}


def _verb_to_feed_type(verb):
    type_str = _VERB_TO_FEED_TYPE_MAP.get(verb, None)
    if type_str is None:
        raise UnimplementedException(
            'Unknown feed verb: {0}'.format(verb)
        )
    return getattr(FeedType, type_str)


def _type_to_feed_type(t):
    type_str = _TYPE_TO_FEED_TYPE_MAP.get(t, None)
    if type_str is None:
        raise UnimplementedException(
            'Unknown feed type: {0}'.format(t)
        )
    return getattr(FeedType, type_str)


class Feed(object):
    """
    表示用户首页信息流里的单个卡片数据。用户一般无法手动构造此对象，而需要通过
    :any:`Me.feeds` 属性来获取 Feed Generator

    使用示例：

    ..  code-block:: Python

        from zhihu_oauth import ZhihuClient, FeedType

        # your login code

        me = client.me()

        for feed in me.feeds:
            if feed.type is FeedType.VOTEUP_ANSWER:
                print(feed.action_text)

    或者使用 Feed Generator 的 filter 函数来获取指定类型的 Feed：

    ..  code-block:: Python

        for feed in me.feeds.filter({
            FeedType.VOTEUP_ANSWER, FeedType.ANSWER_FROM_TOPIC,
            FeedType.CREATE_ANSWER, FeedType.COLLECT_ANSWER,
        }):
            ans = feed.target
            print(ans.question.title, ans.author.name, ans.voteup_count)
    """

    def __init__(self, data, session):
        self._data = data
        self._session = session
        if self._data.get('type', None) == 'feed':
            self._type = _verb_to_feed_type(self._data['verb'])
        else:
            self._type = _type_to_feed_type(self._data['type'])

    @property
    def action_text(self):
        """
        描述此 Feed 的文字，如 「XXX 赞同了回答」，「XXX 发表了文章」
        """
        if self.type is not FeedType.CARD:
            return self._data['action_text']

    @property
    def created_time(self):
        """
        Feed 时间戳
        """
        if self.type not in _NON_TRIVIAL_FEED_TYPES:
            return self._data['created_time']

    @property
    def target(self):
        """
        Feed 的主要内容。

        `target` 在不同 :any:`Feed.type` 下有不同的类型。

        参见 :any:`FeedType`
        """
        if self.type not in _NON_TRIVIAL_FEED_TYPES:
            if self.type in {
                FeedType.FOLLOW_ROUNDTABLE, FeedType.VOTEUP_EBOOK,
                FeedType.EBOOK_FROM_TOPIC,
            }:
                return StreamingJSON(self._data['target'])
            return build_zhihu_obj_from_dict(
                self._data['target'], self._session
            )

    @property
    def type(self):
        """
        Feed 的类型。

        参见 :any:`FeedType`
        """
        return self._type

    @property
    def actors(self):
        """
        可以理解为 Feed 的来源（可能有多个），所以是一个 Generator。

        对于 ``XXX_FROM_TOPIC`` 类型的 Feed，此属性为 :any:`Topic` 对象，
        其他类型时大多为 :any:`People` 型。

        卡片和广告型 Feed 没有此内容。
        """
        if self.type not in _NON_TRIVIAL_FEED_TYPES:
            for actor_data in self._data['actors']:
                yield build_zhihu_obj_from_dict(actor_data, self._session)

    @property
    def promotions(self):
        """
        ``ACTION_CARD`` 型 Feed 专属属性，表示促销的内容列表，是一个 Generator
        """
        if self.type is FeedType.ACTION_CARD:
            for card in self._data['card']['promotion_list']:
                yield build_zhihu_obj_from_dict(
                    card['elem'], self._session, type_name=card['type'],
                )

    @property
    def ad(self):
        """
        ``AD`` 型 Feed 专属属性，表示广告内容。

        因为应该没什么人用，所以直接返回了 JSON 内容的 :any:`StreamingJSON` 封装
        """
        if self.type is FeedType.AD:
            return StreamingJSON(self._data['ad'])
