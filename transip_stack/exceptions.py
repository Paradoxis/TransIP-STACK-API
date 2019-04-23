from requests import Response


class StackException(Exception):
    def __init__(self, msg, resp: Response = None):
        super(StackException, self).__init__(msg)
        self.response = resp
