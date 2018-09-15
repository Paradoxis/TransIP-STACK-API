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

    @name.setter
    def name(self, value: str):
        self._props["displayName"] = value

    @property
    def username(self) -> str:
        return self._props.get("username", "")

    @username.setter
    def username(self, value: str):
        self._props["username"] = value

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

    @disk_quota.setter
    def disk_quota(self, value: Optional[int]):
        self._props["quota"] = int(value) if value else self.QUOTA_INFINITE

    @property
    def disk_used(self) -> int:
        return int(self._props.get("used"))

    @property
    def language(self) -> str:
        return self._props.get("language", "nl_NL")

    @language.setter
    def language(self, value):
        self._props["language"] = value

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

    def save(self):
        """
        Save the current user state
        :return: None
        """
        resp = self._http.post("/api/users/update", json=[
            {"action": "update", "user": self._props}
        ], csrf=True).json()

        if resp.get("status") != "ok":
            raise StackException(
                "Unable to set properties. Expected status 'ok' "
                "and got response: {}".format(resp))

    def __repr__(self):
        return "<StackUser name={!r}>".format(self.name)