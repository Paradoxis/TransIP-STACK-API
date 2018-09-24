from functools import lru_cache

from requests import Session
from bs4 import BeautifulSoup

from transip_stack import __version__


class StackHTTP(Session):

    def __init__(self, hostname: str):
        super(StackHTTP, self).__init__()
        self.__host = hostname
        self.__base = "https://{}".format(hostname)
        self.expose_agent = True

    def request(self, method, url, *args, **kwargs):
        headers = kwargs.get("headers", {})

        if self.expose_agent:
            headers["User-Agent"] = "Python-STACK-API/{}".format(__version__)

        if kwargs.pop("csrf", True):
            headers["X-CSRF-Token"] = self.csrf_token

        kwargs["headers"] = headers

        return super(StackHTTP, self).request(method, self.__base + url, *args, **kwargs)

    @property
    def base_url(self):
        return self.__base

    @property
    @lru_cache()
    def csrf_token(self):
        resp = self.get("/files", csrf=False)
        soup = BeautifulSoup(resp.text, "html.parser")
        return soup.find("meta", {"name": "csrf-token"}).attrs.get("content").strip()