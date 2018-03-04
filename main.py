from login import Login
from topic import Topic



if __name__ == '__main__':

    client = Login().client_login()
    topic = Topic(client)

    root_id = 19776749
    info = topic.info(root_id)
    print(info)