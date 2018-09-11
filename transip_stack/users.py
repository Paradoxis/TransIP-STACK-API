from typing import Optional

from transip_stack.exceptions import StackException


class StackUser:
    """
    Base class of a STACK user
    """
    QUOTA_INFINITE = -1

    def __init__(self, stack, props: dict=None):
        """
        StackUser constructor
        :param stack: Instance of the current STACK object
        :param props: Properties of the current node
        :type stack: transip_stack.stack.Stack
        """
        self._props = props or {}
        self._stack = stack
        self._http = stack.http
        self._webdav = stack.webdav

    @property
    def name(self) -> str:
        return self._props.get("displayName", "")

    @property
    def username(self) -> str:
        return self._props.get("username", "")

    @property
    def is_admin(self) -> bool:
        return self._props.get("isAdmin", False)

    @property
    def is_premium(self) -> bool:
        return self._props.get("isPremium", False)

    @property
    def disk_quota(self) -> Optional[int]:
        quota = int(self._props.get("quota", self.QUOTA_INFINITE))
        return quota if (quota > 0) else None

    @property
    def disk_used(self) -> int:
        return int(self._props.get("used"))

    def delete(self):
        """
        Delete the current user
        :return: None
        """
        data = {"action": "delete", "user": self._props}
        resp = self._http.post("/api/users/update", json=[data], csrf=True).json()

        if not resp.get("status") == "ok":
            raise StackException(
                "Unable to delete user '{}', expected status 'ok' "
                "and got response: {}".format(self.username, resp))

    def set_password(self, password: str):
        """
        Set the password of the current user
        :param password: Password to set
        :return: None
        """
        data = self._props.copy()
        data["password"] = password
        resp = self._http.post("/api/users/update", json=[
            {"action": "update", "user": data}
        ], csrf=True).json()

        if not resp.get("status") == "ok":
            raise StackException(
                "Unable to set user password '{}', expected status 'ok' "
                "and got response: {}".format(self.username, resp))

    def set_disk_quota(self, disk_quota: int):
        """
        Set the disk quota of the current user
        :param disk_quota:
            Disk quota to set, if set to None, an
            infinite amount will be assigned
        :return: None
        """
        data = self._props.copy()
        data["quota"] = int(disk_quota) if disk_quota else self.QUOTA_INFINITE

        resp = self._http.post("/api/users/update", json=[
            {"action": "update", "user": data}
        ], csrf=True).json()

        if resp.get("status") == "ok":
            self._props.update(data)
        else:
            raise StackException(
                "Unable to set user password '{}', expected status 'ok' "
                "and got response: {}".format(self.username, resp))

    def set_name(self, name: str):
        """
        Set the display name of the current user
        :param name: New name to set
        :return: None
        """
        data = self._props.copy()
        data["displayName"] = name

        resp = self._http.post("/api/users/update", json=[
            {"action": "update", "user": data}
        ], csrf=True).json()

        if resp.get("status") == "ok":
            self._props.update(data)
        else:
            raise StackException(
                "Unable to set user's name '{}', expected status 'ok' "
                "and got response: {}".format(self.username, resp))
