from functools import lru_cache

from requests import Session
from bs4 import BeautifulSoup

from transip_stack import __version__


class StackHTTP(Session):

    def __init__(self, hostname: str, username: str, password: str):
        super(StackHTTP, self).__init__()
        self.__host = hostname
        self.__base = "https://{}".format(hostname)

        self.__username = username
        self.__password = password

        self.expose_agent = True

    def request(self, method, url, *args, **kwargs):
        """
        Custom overload of the `requests.request` method
        :param method: Method to use
        :param url: URL to call (automatically prepends the the base url to it
        :return: Server response
        """
        headers = kwargs.get("headers", {})

        if self.expose_agent:
            headers["User-Agent"] = "Python-STACK-API/{}".format(__version__)

        if kwargs.pop("csrf", True):
            headers["X-CSRF-Token"] = self.csrf_token

        kwargs["headers"] = headers

        return super(StackHTTP, self).request(method, self.__base + url, *args, **kwargs)

    def webdav(self, method, url, *args, **kwargs):
        """
        Makes a WebDAV request

        :param method:
            WebDAV method, see the following link for more information:
            https://www.qed42.com/blog/using-curl-commands-webdav

        :param url:
            Endpoint to call, already has the required prefix automatically
            prepended to it.

        :return: Response from the server
        """
        url = '/remote.php/webdav/' + url.lstrip('/')
        auth = (self.__username, self.__password)
        return self.request(method, url, csrf=False, auth=auth, *args, **kwargs)

    @property
    def base_url(self):
        return self.__base

    @property
    def webdav_base_url(self):
        return self.__base + '/remote.php/webdav/'

    @property
    @lru_cache()
    def csrf_token(self):
        resp = self.get("/files", csrf=False)
        soup = BeautifulSoup(resp.text, "html.parser")
        return soup.find("meta", {"name": "csrf-token"}).attrs.get("content").strip()