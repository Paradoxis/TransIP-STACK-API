from posixpath import basename
from datetime import date
from typing import Union

from .exceptions import StackException


class StackNode:
    """
    Base class of a STACK node
    All nodes have the following keys:
        
        * fileId: int
        * path: str
        * mimetype: str
        * etag: str
        * shareToken: str
        * expirationDate: str
        * hasSharePassword: bool
        * shareTime: int
        * canUpload: bool
        * fileSize: int
        * isFavorited: bool
        * mtime: int
        * isPreviewable: bool
        * width: int
        * height: int
    """

    def __init__(self, stack, props: dict=None):
        """
        StackNode constructor
        :param stack: Instance of the current STACK object
        :param props: Properties of the current node
        :type stack: transip_stack.stack.Stack
        """
        self._props = props or {}
        self._stack = stack
        self._http = stack.http
        self._webdav = stack.webdav

    @property
    def exists(self) -> bool:
        return self._props.get("exists", True)

    @property
    def type(self) -> str:
        return self._props.get("mimetype")

    @property
    def size(self):
        return self._props.get("fileSize", 0)

    @property
    def name(self):
        return basename(self.path)

    @property
    def path(self):
        return self._props.get("path", "")

    @property
    def is_shared(self) -> bool:
        return any(self._props.get("shareToken", ""))

    @property
    def has_share_password(self) -> bool:
        if not self.is_shared:
            return self._props.get("hasSharePassword", False)
        else:
            raise StackException("File '{}' is not shared!".format(self.path))

    @property
    def share_token(self) -> str:
        if self.is_shared:
            return self._props.get("shareToken", "")
        else:
            raise StackException("File '{}' is not shared!".format(self.path))

    @property
    def share_url(self) -> str:
        if self.is_shared:
            return "{}/s/{}".format(self._http.base_url, self.share_token)
        else:
            raise StackException("File '{}' is not shared!".format(self.path))

    def share(self, password: str=None, expiry_date: Union[date, str]=None) -> str:
        """
        Share a file, auto-returns the share URL
        :param password: Password protect the share
        :param expiry_date: Set an expiry date on the share
        :return: 
        """
        data = {"action": "share", "path": self.path, "active": True, "allowWrites": False,
                "updatePassword": True, "updateExpireDate": True, "sharePassword": password or ""}

        if isinstance(expiry_date, date):
            data["expireDate"] = date(expiry_date).strftime("%Y-%m-%d")
        else:
            data["expireDate"] = expiry_date or ""

        resp = self._http.post("/api/files/update", json=[data], csrf=True)
        self._props.update(resp.json()[0])
        return self.share_url

    def unshare(self):
        """
        Un-share a file
        :return: None
        """
        data = {"action": "share", "path": self.path, "active": False, "allowWrites": False}
        resp = self._http.post("/api/files/update", json=[data], csrf=True)
        self._props.update(resp.json()[0])

    def delete(self):
        """
        Deletes a file
        :return: None
        """
        data = {"action": "delete", "path": self.path, "query": ""}
        self._http.post("/api/files/update", json=[data], csrf=True)


class StackDirectory(StackNode):
    """
    Instance of a directory on stack
    """


class StackFile(StackNode):
    """
    Instance of a file on stack
    """
