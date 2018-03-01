# coding:utf-8
import json

from network import Urllib2
from login import Login


class Topic():
    def __init__(self):
        self.base_url = 'https://www.zhihu.com/api/v4/topics/'
        self.urllib = Urllib2()
        self.client = Login().client_login()

    def info(self, tid, debug=False):
        url = self.base_url + str(tid)
        res = self.client._session.request('GET', url=url)  
        ret_json = json.loads(res.text)

        if 'error' in ret_json:
            print(json)
            return 

        info_dict = {}
        info_list = [   'id', 'name', 'questions_count', 'unanswered_count',
                        'best_answerers_count', 'best_answerers_count',
                        'father_count', 'followers_count' 
                    ]
        for item in info_list:
            info_dict[item] = ret_json.get(item)

        if debug:
            for key in info_dict:
                print(key, ':', info_dict.get(key))

        return info_dict

    def get_children(self, tid, limit=50, offset=0):
        param = '?limit=' + str(limit) + '&offset=' + str(offset)
        url = self.base_url + str(tid) + '/children' + param
        res = self.client._session.request('GET', url=url)  
        ret_json = json.loads(res.text)
        if 'error' in ret_json:
            print(json)
            return []  

        if ret_json.get('paging').get('is_end'):
            return []

        # Children in this page
        children_list = []
        for topic in ret_json.get('data'):
            name = topic.get('name')
            tid = topic.get('id')
            children_list.append([name, tid])

        # Children in other page
        offset += limit
        rest_children = get_children(tid, limit, offset)
        return children_list.extend(rest_children)

    def get_all_sub_topic(self, tid):
        # TODO modify:
        all_topic = {}
        # get topic info
        info_dict = self.info(tid)
        name = info_dict.get('name')
        all_topic[name] = info_dict

        # get topic's direct children list
        direct_children = self.get_children(tid)
        info_dict['children'] = direct_children

        # Process all children's children
        children_info = {}
        for name, tid in direct_children:
            children_info = self.get_all_sub_topic(tid)

        info_dict['children_info'] = children_info

        return all_topic


if __name__ == '__main__':
    root_id = 19776749
    topic = Topic()
    for i in range(3000):
        print(i)
        topic.info(root_id)