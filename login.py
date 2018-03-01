# coding=utf-8

from __future__ import unicode_literals, print_function

import os
import sys
import base64

from zhihu_oauth import ZhihuClient

class Login():
    def __init__(self):
        self.TOKEN_FILE = 'token.pkl.' + str(sys.version_info[0])
        self.client = ZhihuClient()

    def client_login(self):
        if not os.path.isfile(self.TOKEN_FILE):
            self.client.login_in_terminal()
            self.client.save_token(self.TOKEN_FILE)
        else:
            self.client.load_token(self.TOKEN_FILE)
        return self.client