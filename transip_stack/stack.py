import logging
from io import BytesIO, BufferedIOBase
from typing import Union, Iterable
from posixpath import join, realpath

from webdav.client import Client as WebdavClient
from webdav.exceptions import WebDavException

from transip_stack.http import StackHTTP
from transip_stack.users import StackUser
from transip_stack.nodes import StackNode, StackFile, StackDirectory
from transip_stack.exceptions import StackException


class Stack:
    """
    TransIP STACK API
    Note: This is an unofficial API and may be deprecated at any time
    """

    def __init__(self, username: str, password: str, hostname: str):
        """
        STACK constructor
        """
        self.__username = username
        self.__password = password
        self.__hostname = hostname

        self.__logged_in = False
        self.__cwd = "/"

        self.ls_buffer_limit = 1000           # Default: 50
        self.enforce_password_policy = False  # Yeah, passwords aren't enforced server side.

        self.http = StackHTTP(hostname)
        self.webdav = WebdavClient({
            'webdav_root': 'remote.php/webdav/',
            'webdav_login': username,
            'webdav_password': password,
            'webdav_hostname': "https://{}".format(hostname),
        })

        self.webdav.default_options["WRITEFUNCTION"] = lambda x: None

    def __enter__(self):
        """
        Context manager enter, for use in the 'with' statement
        Automatically logs the user in
        :return: None
        """
        self.login()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Context manager exit, logs the user out if they're logged in
        :return: None
        """
        if self.__logged_in:
            self.logout()

    @property
    def authenticated(self) -> bool:
        """
        Is this current session authenticated?
        :return: True if logged in
        """
        return self.__logged_in

    def login(self) -> None:
        """
        Log into STACK
        :return: None
        :raises: StackException
        """
        data = {"username": self.__username, "password": self.__password}
        resp = self.http.post("/login", data=data, allow_redirects=False, csrf=False)
        self.__logged_in = resp.status_code in (301, 302)

        if self.__logged_in:
            logging.debug("Logged in successfully")
        else:
            logging.debug("No redirect detected in login request, invalid password.")
            raise StackException("Invalid username or password.")

    def logout(self) -> None:
        """
        Log out of STACK
        :return: None
        """
        self.http.get("/logout", allow_redirects=False, csrf=False)
        self.__logged_in = False
        logging.debug("Logged out successfully")

    @property
    def cwd(self) -> str:
        """
        Get the current working directory
        :return: Current working directory
        """
        return self.__cwd.rstrip('/') + '/'

    @property
    def pwd(self) -> str:
        """
        Alias of cwd
        :return: Current working directory
        """
        return self.cwd

    def __files(self, path: str, offset: int, query: str="", order: str="asc") -> dict:
        """
        Load the files metadata of the current directory
        :return: None
        """
        params = {
            "dir": path, "type": "files", "public": "false",
            "offset": offset, "limit": self.ls_buffer_limit,
            "sortBy": "default", "order": order, "query": query}

        return self.http.get("/api/files", params=params).json()

    def cd(self, path: str="/") -> StackDirectory:
        """
        Change the current STACK working directory
        :param path: Path to change to, default is the root directory ('/')
        :return: StackDirectory
        """
        if path.startswith("/"):
            path = path
        else:
            path = realpath(join(self.__cwd, path))

        directory = self.directory(path)
        self.__cwd = path
        return directory

    def walk(self, path: str=None, order: str="asc") -> Iterable[StackFile]:
        """
        Recursively walk through the entire directory tree, yielding
        each file in all directories

        :param path: Starting path to walk
        :param order: Walk order (asc, desc)
        :return: Generator of StackFile's
        """
        if order not in ('asc', 'desc'):
            raise StackException('Invalid order: {!r}, accepted values: asc, desc'.format(order))

        if not path:
            path = self.__cwd

        for node in self.ls(path=path, order=order):
            if isinstance(node, StackDirectory):
                yield from self.walk(node.path, order=order)
            else:
                yield node

    def ls(self, search: str="", order: str="asc", path: str=None) -> Iterable[Union[StackFile, StackDirectory]]:
        """
        List the current (or other) directory
        :param path: Path to list, optional (default: CWD)
        :param search: Search files with a given name
        :param order: What way should the files be ordered? 
        :return: StackNode iterator
        """
        if order not in ("asc", "desc"):
            raise StackException(
                "Invalid order parameter, got '{}', allowed "
                "values: 'asc', 'desc'".format(order))

        if not path:
            path = self.__cwd

        offset = 0
        amount = None

        while amount is None or (amount is not None and offset < int(amount)):
            files = self.__files(path, offset, query=search, order=order)
            offset += self.ls_buffer_limit
            amount = int(files.get("amount"))
            yield from self.__nodes_to_objects(files.get("nodes") or [])

    def __nodes_to_objects(self, nodes: list) -> Iterable[StackNode]:
        """
        Converts a list of STACK file/directory nodes to an object iterator
        :return: Iterator
        """
        for node in nodes:
            yield self.__node_to_object(node)

    @property
    def files(self) -> Iterable[StackFile]:
        """
        Get all files in the current directory
        :return: Iterator with only StackFile objects
        """
        yield from (node for node in self.ls() if isinstance(node, StackFile))

    @property
    def directories(self) -> Iterable[StackDirectory]:
        """
        Get all sub-directories in the current directory
        :return: Iterator with only StackDirectory objects
        """
        yield from (node for node in self.ls() if isinstance(node, StackDirectory))

    def __node_to_object(self, node: dict):
        """
        Convert a stack node to the correct object by
        checking it's MIME type
        :param node: Node properties
        :return: Stack node
        """
        if node.get("mimetype") == "httpd/unix-directory":
            return StackDirectory(stack=self, props=node)
        else:
            return StackFile(stack=self, props=node)

    def __node(self, name: str):
        """
        Get a node by name
        :param name: Node name to find
        :return: Node object
        """
        if name.startswith("/"):
            path = name
        else:
            path = join(self.__cwd, name)

        resp = self.http.get("/api/pathinfo", params={"path": path})

        if resp.status_code == 404:
            raise StackException('No such file or directory.')

        if resp.status_code != 200:
            raise StackException(resp.text.strip())

        return self.__node_to_object(resp.json())

    def file(self, name: str) -> StackFile:
        """
        Get a file by name
        :param name: Name to find
        :return: File object
        """
        node = self.__node(name)

        if isinstance(node, StackDirectory):
            raise StackException("File '{}' is a directory!".format(name))

        return node

    def directory(self, name: str) -> StackDirectory:
        """
        Get a directory by name
        :param name: Name to find
        :return: Directory object
        """
        node = self.__node(name)

        if isinstance(node, StackFile):
            raise StackException("Directory '{}' is a file!".format(name))

        return node

    def upload(self, file, *, name: str=None, path: str=None) -> StackFile:
        """
        Upload a file to Stack
        :param file: IO pointer or string containing a path to a file
        :param name:
            Custom name which will be used on
            the remote server, defaults to file.name
        :param path: Path to upload it to, defaults to current working directory
        :return: Instance of a stack file
        """
        if not path:
            path = self.__cwd

        if hasattr(file, 'read'):
            return self.__upload(file=file, path=path, name=name)

        if isinstance(file, str):
            with open(file, "rb") as fd:
                return self.__upload(file=fd, path=path, name=name)

        raise StackException(
            "File should either be a path to a file on "
            "disk or an IO type, got: {}".format(type(file)))

    def __upload(self, file, path: str=None, name: str=None) -> StackFile:
        """
        Core logic of the upload, previous method simply converts the name
        to a file IO pointer and passes it to this method
        :param file: File pointer
        :param path: Remote path
        :param name: Remote name
        :return: StackFile instance
        """
        if not name and not getattr(file, 'name', None):
            raise StackException(
                "Unable to determine remote file name, either set "
                "it via file.name or by passing the 'name' parameter")

        name = name or file.name
        path = join(path, name)

        try:
            self.webdav.upload_from(file, path)
            return self.file(path)

        except WebDavException as e:
            raise StackException(e)

    def download(self, file: str, output_path: str, remote_path: str=None) -> None:
        """
        Download a file from your STACK account to a given path
        :param file: File name to download 
        :param remote_path:
            Directory to download from (default: current working directory)
        :param output_path: Output path to write the file to
        :return: None
        """
        if not remote_path:
            remote_path = self.__cwd

        file = join(remote_path, file.lstrip("/"))

        try:
            self.webdav.download(file.lstrip("/"), output_path)

        except WebDavException as e:
            raise StackException(e)

    def download_into(self, file: str, buffer: Union[BufferedIOBase, BytesIO]=None, remote_path: str=None):
        """
        Download a file from your STACK account
        :param file: File name to download
        :param remote_path: Path to find the file in
        :param buffer: Buffer to download into (BytesIO, StringIO, file pointer)
        :return: BytesIO buffer
        """
        if not remote_path:
            remote_path = self.__cwd

        file = join(remote_path, file.lstrip("/"))

        if not buffer:
            buffer = BytesIO()

        if not hasattr(buffer, 'write'):
            raise StackException(
                "Download buffer must be a binary IO type, please "
                "use BytesIO or open your file in 'wb' mode.")

        try:
            self.webdav.download_to(buffer, file.lstrip("/"))
            buffer.seek(0)
            return buffer

        except WebDavException as e:
            raise StackException(e)

    def mkdir(self, name: str, path: str=None) -> StackDirectory:
        """
        Make a new directory
        :param name: Directory name to create
        :param path: Directory to create it in
        :return: StackDirectory
        """
        if not path:
            path = self.__cwd

        path = join(path, name)

        try:
            self.webdav.mkdir(path)
            return self.directory(path)

        except WebDavException as e:
            raise StackException(e)

    @property
    def users(self) -> Iterable[StackUser]:
        """
        Get an iterator of all users registered to this account
        :return: StackUser iterator
        """
        limit = 50
        offset = 0
        amount = None

        while amount is None or (amount is not None and offset < int(amount)):
            params = {"public": False, "offset": offset, "limit": limit, "query": ""}
            resp = self.http.get("/api/users", params=params)

            if resp.status_code == 403:
                raise StackException(
                    'Unable to list users, access denied. '
                    'Please log in with the administrator account.')

            users = resp.json()

            yield from (StackUser(stack=self, props=u) for u in users.get("users") or [])

            amount = int(users.get("amountUsers"))
            offset += limit

    def user(self, name: str) -> StackUser:
        """
        Get a user by name
        :param name: Name to find
        :return: Stack user
        """
        params = {"public": False, "offset": 0, "limit": 1, "query": name}
        users = self.http.get("/api/users", params=params)

        if users.status_code == 403:
            raise StackException(
                'Unable to list users, access denied. '
                'Please log in with the administrator account.')

        users = users.json()

        if not any(users.get("users") or []):
            raise StackException("Unable to find user '{}'".format(name))

        return StackUser(stack=self, props=users.get("users", [])[0])

    def create_user(self, name: str, username: str, password: str, disk_quota: int=None) -> StackUser:
        """
        Create a STACK user
        :param name: User to create
        :param username: Username
        :param password: Password
        :param disk_quota: Disk quota in bytes, if set to None user is allowed to use infinite space
        :return: The newly created stack user
        """
        if self.enforce_password_policy:
            if len(password) < 8:
                raise StackException("Password must be at least 8 characters long!")

        disk_quota = int(disk_quota) if disk_quota else -1
        data = {
            "action": "create", "user": {
                "username": username, "newUser": True, "isPublic": False,
                "password": password, "displayName": name, "quota": disk_quota}}

        resp = self.http.post("/api/users/update", json=[data])

        if resp.status_code == 409:
            raise StackException(
                "Unable to create user '{}', either you don't have permission "
                "to do so or the user already exists!".format(username))

        resp = resp.json()

        if resp.get("status") != "ok":
            raise StackException("Expected 'ok' status, got response: {}".format(resp))

        return self.user(username)

    def user_or_create_new(self, name: str, username: str, password: str, disk_quota: int=None) -> StackUser:
        """
        Get a user on STACK or create a new one if not found
        :param name: Name of the user
        :param username: Username, used when searching
        :param password: Password to set if the user isn't found
        :param disk_quota: Disk quota to set in bytes, default: Infinite
        :return: Stack User
        """
        try:
            return self.user(username)

        except StackException:
            return self.create_user(name, username, password, disk_quota)