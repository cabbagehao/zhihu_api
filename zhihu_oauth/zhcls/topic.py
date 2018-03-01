# coding=utf-8

from __future__ import unicode_literals

from .base import Base
from .generator import generator_of
from .normal import normal_attr
from .other import other_obj
from .urls import (
    TOPIC_ACTIVITIES_URL,
    TOPIC_BEST_ANSWERERS_URL,
    TOPIC_BEST_ANSWERS_URL,
    TOPIC_CHILDREN_URL,
    TOPIC_DETAIL_URL,
    TOPIC_FOLLOWERS_URL,
    TOPIC_INDEX_URL,
    TOPIC_PARENTS_URL,
    TOPIC_UNANSWERED_QUESTION,
)
from .utils import build_zhihu_obj_from_dict, int_id

__all__ = ['Topic', 'TopicIndex', "TopicIndexSection"]


class Topic(Base):
    @int_id
    def __init__(self, tid, cache, session):
        super(Topic, self).__init__(tid, cache, session)

    def _build_url(self):
        return TOPIC_DETAIL_URL.format(self.id)

    # ---- simple info -----

    @property
    @normal_attr()
    def avatar_url(self):
        return None

    @property
    @normal_attr('best_answers_count')
    def best_answer_count(self):
        return None

    @property
    def best_answers_count(self):
        return self.best_answer_count

    @property
    @normal_attr()
    def excerpt(self):
        return None

    @property
    def father_count(self):
        return self.parent_count

    @property
    @normal_attr('followers_count')
    def follower_count(self):
        return None

    @property
    def followers_count(self):
        return self.follower_count

    @property
    @other_obj("TopicIndex", module_filename='topic')
    def index(self):
        """
        话题索引

        :rtype: :any:`TopicIndex`
        """
        return {'id': self.id}

    @property
    @normal_attr()
    def introduction(self):
        return None

    @property
    @normal_attr()
    def name(self):
        return None

    @property
    @normal_attr('father_count')
    def parent_count(self):
        return None

    @property
    @normal_attr('questions_count')
    def question_count(self):
        return None

    @property
    def questions_count(self):
        return self.question_count

    @property
    @normal_attr()
    def unanswered_count(self):
        return None

    # ----- generators -----

    @property
    @generator_of(TOPIC_ACTIVITIES_URL, 'TopicActivity')
    def activities(self):
        """
        :any:`Question` 和 :any:`Answer` 的混合迭代器，使用时注意判断。

        ..  code-block:: Python

            for act in topic.activities:
                if isinstance(act, Answer):
                    # pass
                else:
                    assert(isinstance(act, Question))
                    # pass
        """
        return None

    @property
    @generator_of(TOPIC_BEST_ANSWERS_URL, 'answer')
    def best_answers(self):
        """
        精华回答
        """
        return None

    @property
    @generator_of(TOPIC_BEST_ANSWERERS_URL, 'people')
    def best_answerers(self):
        """
        好像叫，最佳回答者吧……

        best_answerers……知乎真会起名字……
        """
        return None

    @property
    @generator_of(TOPIC_CHILDREN_URL, 'topic')
    def children(self):
        """
        子话题
        """
        return None

    @property
    @generator_of(TOPIC_FOLLOWERS_URL, 'people')
    def followers(self):
        return None

    @property
    @generator_of(TOPIC_PARENTS_URL, 'topic')
    def parents(self):
        """
        父话题
        """
        return None

    @property
    @generator_of(TOPIC_UNANSWERED_QUESTION, 'question')
    def unanswered_questions(self):
        """
        其实基本上就等于「所有问题」，知乎客户端上的所有问题选项卡就是用的这个接口。
        """
        return None


class TopicIndex(Base):
    _SECTIONS_KEY = 'topic_index_modules'
    _EDITORS_KEY = 'topic_index_editors'

    @int_id
    def __init__(self, tiid, cache, session):
        super(TopicIndex, self).__init__(tiid, cache, session)
        self._get_data()

    def _build_url(self):
        return TOPIC_INDEX_URL.format(self.id)

    # ---------- simple info ---------

    @property
    def id(self):
        """
        没什么用，获取到的其实是对应 Topic 的 ID
        """
        return self._id

    # ---------- generators ---------

    @property
    def sections(self):
        """
        话题索引分为各个部分，这个属性是各个部分的迭代器。

        用法示例：

        ..  code-block:: Python

            for section in topic.index.sections:
                print(section.title)
                # Other operator of section

        :rtype: :any:`TopicIndexSection` 的迭代器
        """
        for data in self._data[self._SECTIONS_KEY]:
            yield TopicIndexSection(data, self._session)

    @property
    def editors(self):
        """
        ..  code-block:: Python

            for people in topic.index.editors:
                print(people.name)
                # Other operator of people

        :rtype: 索引编辑者（:any:`People` 对象）的迭代器。
        """
        for data in self._data[self._EDITORS_KEY]:
            yield build_zhihu_obj_from_dict(data, self._session)


class TopicIndexSection(object):
    """
    自身是一个 :any:`Question` 对象的迭代器，附带了 title 属性和另一个相关话题的迭代器。

    ..  code-block:: Python

        for section in topic.index.sections:
            print(section.title, ':')
            for question in section:
                print(question.title)
            for topic in section.related_topics:
                print(topic.name)
    """
    _TYPE_KEY = 'type'
    _SECTION_INDICATOR = 'topic_index_module'
    _SECTION_DATA_LIST_KEY = 'items'
    _RELATED_TOPICS_KEY = 'relatedtopics'
    _TITLE_KEY = 'title'

    def __init__(self, data, session):
        if data[self._TYPE_KEY] != self._SECTION_INDICATOR:
            raise ValueError("Must be a {} type dict, {} provided".format(
                self._SECTION_INDICATOR, data
            ))
        self._data = data
        self._session = session

        self._index = 0
        self._len = len(self._data[self._SECTION_DATA_LIST_KEY])

    # ---------- simple info ---------

    @property
    def title(self):
        return self._data[self._TITLE_KEY]

    # ---------- generator ----------

    @property
    def related_topics(self):
        """
        :rtype: :any:`Topic` 对象的迭代器
        """
        for data in self._data[self._RELATED_TOPICS_KEY]:
            yield build_zhihu_obj_from_dict(data, self._session)

    # ---------- self as a generator ---------

    def __iter__(self):
        self._index = 0
        return self

    def __len__(self):
        return self._len

    def __next__(self):
        try:
            obj = self[self._index]
        except IndexError:
            self._index = 0
            raise StopIteration
        self._index += 1
        return obj

    next = __next__

    def __getitem__(self, item):

        if not isinstance(item, int):
            raise TypeError('Need an int as index, not {0}'.format(type(item)))

        if item >= self._len:
            raise IndexError()

        data = self._data[self._SECTION_DATA_LIST_KEY][item]
        return build_zhihu_obj_from_dict(data, self._session)
