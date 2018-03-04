# coding:utf-8
import json

from network import Urllib2


class Topic():
    def __init__(self, client):
        self.base_url = 'https://www.zhih2u.com/api/v4/topics/'
        self.urllib = Urllib2()
        self.client = client

    def info(self, tid):
        url = self.base_url + str(tid)
        res = self.client._session.request('GET', url=url)  
        ret_json = json.loads(res.text)
        if 'error' in ret_json:
            print(json)
            return {}

        info_dict = {}
        info_list = [   'id', 'name', 'questions_count', 'unanswered_count',
                        'best_answerers_count', 'best_answerers_count',
                        'father_count', 'followers_count' 
                    ]
        for item in info_list:
            info_dict[item] = ret_json.get(item)
        return info_dict

    def get_children(self, tid, limit=10, offset=0):
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
            c_name = topic.get('name')
            c_tid = topic.get('id')
            children_list.append([c_name, c_tid])

        # Children in other page
        offset += limit
        rest_children = self.get_children(tid, limit, offset)
        return children_list + rest_children

    def get_offspring(self, tid, level=1):
        # Get topic information.
        topics = {}
        info = self.info(tid)
        topics['name'] = info.get('name')
        topics['info'] = info
        topics['level'] = level
        topics['children'] = []
        print('    ' * (level-1) + topics['name'])

        # Get topic's direct children list
        if int(tid) == 19776751: 
            return topics  # No class topic.
        children = self.get_children(tid)
        for c_name, c_tid in children:
            c_info = self.get_offspring(c_tid, level+1)
            topics['children'].append(c_info)

        return topics

    def dump_to_file(self, dict_data):
        # with open('topics.json', 'w+') as f: 
        import codecs 
        with codecs.open('topics.json', 'w+', encoding="utf-8") as f:
            json.dump(dict_data, f, indent=4, ensure_ascii=False)

if __name__ == '__main__':
    from login import Login
    client = Login().client_login()
    topic = Topic(client)

    # tid = 19776751
    # info = topic.get_children(tid)
    # print(len(info))

    tid = 19584954
    root_tid = 19776749
    topics_dict = topic.get_offspring(root_tid)
    topic.dump_to_file(topics_dict)
