# coding:utf-8
import os
import json
import time
import copy
import codecs 
import threading
from network import Urllib2


class Topic():
    def __init__(self, client):
        self.topic_file = 'topics.json'
        self.base_url = 'https://www.zhihu.com/api/v4/topics/'
        self.client = client
        self.open_list = []
        self.open_lock = threading.Lock()
        self.topics = self.load_topic_from_file()
        self.topics_lock = threading.Lock()
        self.thread_num = 700

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

    def get_children(self, tid, limit=100, offset=0):
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
            children_list.append(c_tid)

        # Children in other page
        if len(ret_json.get('data')) < limit:
            return children_list

        offset += limit
        rest_children = self.get_children(tid, limit, offset)
        return children_list + rest_children

    def thread_get_topic(self):
        t_name = threading.current_thread().getName()
        while self.open_list:
            # Get item from open list
            with self.open_lock:
                if len(self.open_list) > self.thread_num:
                    get_num = 10
                else:
                    get_num = 2
                local_list = self.open_list[0:get_num]
                self.open_list = self.open_list[get_num:]

            while local_list:
                tid, level = local_list.pop(0)
                if tid in self.topics:
                    continue
                info = self.info(tid)
                info['level'] = level
                info['children'] = self.get_children(tid)
                with self.topics_lock:
                    self.topics[info['name']] = info
                
                for c_tid in info['children']:
                    if ((c_tid,level+1) not in self.open_list) and (c_tid not in self.topics):    #TODO
                        local_list.append((c_tid, level+1))
                # If each line have less than 2 tasks, put almost all the local list to queue.
                weight = len(self.open_list) / self.thread_num
                keep_num = 2 + 5*weight
                if weight < 2 and len(local_list) > 10: 
                    self.open_list.extend(local_list[keep_num:])
                    local_list = local_list[:keep_num]

        print('open-list is empty, %s will exit.' %t_name)

    def thread_monitor(self):
        t1 = time.time()
        interval = 30
        init_cnt = len(self.topics)
        last_cnt = init_cnt
        while True:
            if threading.active_count() <= 2 and not self.open_list:
                break
            t2 = time.time()
            with self.topics_lock: 
                self.dump_to_file(self.topics)
            t3 = time.time()

            total_v = (len(self.topics)-init_cnt) / (t3-t1)
            last_v = (len(self.topics)-last_cnt) / interval
            print('Saved %d topics, open: %d, alive: %d, %s, dump time:%.1f, velocity: %d ---> %d' 
                    %(len(self.topics), len(self.open_list), threading.active_count(), time.strftime("%m-%d %H:%M:%S"), t3-t2, total_v, last_v))
            last_cnt = len(self.topics)
            time.sleep(interval)

    def get_offspring(self, root_id):
        self.open_list = [(root_id, 1)]
        thread_list = []
        thread_list.append(threading.Thread(target=self.thread_monitor, name='thread_monitor'))
        for i in range(0, self.thread_num):
            t_name = 'thread_%s' %i
            thread_list.append(threading.Thread(target=self.thread_get_topic, name=t_name))
        
        for thread in thread_list:
            thread.start()
            time.sleep(0.01)
            while not self.open_list:
                time.sleep(0.5)

        for thread in thread_list:
            thread.join()

        self.dump_to_file(self.topics)
        return self.topics

    def load_topic_from_file(self):
        # self.topic_file
        if not os.path.exists(self.topic_file):
            return {}

        with open(self.topic_file, 'r') as f:
            topics = json.loads(f.read())
        print('Restore %d topics.' % len(topics))
        return topics

    def dump_to_file(self, dict_data):
        with codecs.open(self.topic_file, 'w+', encoding="utf-8") as f:
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
