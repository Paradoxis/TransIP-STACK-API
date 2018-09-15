from abc import abstractmethod
from posixpath import basename, dirname, join, realpath
from datetime import date, datetime
from typing import Union

from webdav.exceptions import WebDavException

from transip_stack.exceptions import StackException


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
    @abstractmethod
    def directory(self):
        raise NotImplementedError()

    @property
    def path(self):
        return self._props.get("path", "")

    @property
    def is_favorited(self):
        return self._props.get("isFavorited", False)

    @property
    def is_shared(self) -> bool:
        return any(self._props.get("shareToken", ""))

    @property
    def shared_on(self) -> datetime:
        return datetime.fromtimestamp(self._props.get("shareTime", 0))

    @property
    def share_expiry_date(self):
        ex_date = self._props.get("expirationDate", "")
        if ex_date:
            return datetime.strptime(ex_date, "%Y-%m-%d").date()

    @property
    def has_share_password(self) -> bool:
        if self.is_shared:
            return self._props.get("hasSharePassword", False)

        return False

    @property
    def share_token(self) -> str:
        if self.is_shared:
            return self._props.get("shareToken", "")

    @property
    def share_url(self) -> str:
        if self.is_shared:
            return "{}/s/{}".format(self._http.base_url, self.share_token)

    def share(self, password: str=None, expiry_date: Union[date, datetime, str]=None) -> str:
        """
        Share a file, auto-returns the share URL
        :param password: Password protect the share
        :param expiry_date: Set an expiry date on the share
        :return: 
        """
        data = {"action": "share", "path": self.path, "active": True, "allowWrites": False,
                "updatePassword": True, "updateExpireDate": True, "sharePassword": password or ""}

        if isinstance(expiry_date, (date, datetime)):
            data["expireDate"] = expiry_date.strftime("%Y-%m-%d")
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
        Even though the node is gone, no properties are removed
        This is done so you can use the data even after you delete it
        :return: None
        """
        data = {"action": "delete", "path": self.path, "query": ""}
        self._http.post("/api/files/update", json=[data], csrf=True)

    def refresh(self):
        """
        Refreshes the current object properties by synchronizing it with the server
        :return: None
        """
        resp = self._http.get("/api/pathinfo", params={"path": self.path})

        if resp.status_code != 200:
            pass

        self._props.update(resp.json())

    def move(self, path: str):
        """
        Move the file / directory to another location
        :param path: New path to send to, accepts absolute and relative paths
        :return: None
        """
        if path.endswith("/"):
            path = join(path, self.name)

        if path.startswith("../"):
            path = realpath(join(self.directory, path))
        elif not path.startswith("/") or path.startswith("./"):
            path = join(self.directory, path.lstrip('./'))

        try:
            self._webdav.move(self.path, path)
            self._props["path"] = path
            self.refresh()

        except WebDavException as e:
            raise StackException(e)

    def favorite(self):
        """
        Mark a file or directory as favorited
        :return: None
        """
        data = {"action": "favorite", "path": self.path, "query": "", "active": True}
        resp = self._http.post("/api/files/update", json=[data], csrf=True)
        self._props.update(resp.json()[0])

    def unfavorite(self):
        """
        Un-mark a file or directory as favorited
        :return: None
        """
        data = {"action": "favorite", "path": self.path, "query": "", "active": False}
        resp = self._http.post("/api/files/update", json=[data], csrf=True)
        self._props.update(resp.json()[0])

    def __repr__(self):
        return '<{} name={!r}>'.format(self.__class__.__name__, self.name)


class StackDirectory(StackNode):
    """
    Instance of a directory on stack
    """

    @property
    def directory(self):
        return self.path.rstrip('/') + '/'


class StackFile(StackNode):
    """
    Instance of a file on stack
    """

    @property
    def directory(self) -> str:
        return dirname(self.path).rstrip('/') + '/'
