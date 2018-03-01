import urllib2


class Urllib2():
    def __init__(self):
        pass

    def get(self, url):
        try:
            s = urllib2.urlopen(url)
        except urllib2.HTTPError, e:
            print('urllib2 Error:',e.code, e.msg)
        return s

    def get_content(self, url):
        return self.get(url).read()
