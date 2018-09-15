import sys
import json
from datetime import timedelta, datetime
from io import BytesIO
from os import getenv
from os.path import join
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch, MagicMock

from requests import Response
from webdav.exceptions import WebDavException

from transip_stack import Stack, StackException
from transip_stack.nodes import StackDirectory, StackFile
from transip_stack.users import StackUser


class TransIpStackTestCase(TestCase):
    USERNAME = getenv('STACK_USERNAME')
    PASSWORD = getenv('STACK_PASSWORD')
    HOSTNAME = getenv('STACK_HOSTNAME')
    PREFIX = '.'.join(map(str, sys.version_info)) + '-' + getenv('TRAVIS_COMMIT', 'master')

    @patch.object(Stack, 'logout')
    @patch.object(Stack, 'login')
    def test_connection(self, login, logout):
        with Stack(
            username=self.USERNAME,
            password=self.PASSWORD,
            hostname=self.HOSTNAME
        ) as stack:
            stack._Stack__logged_in = True

        self.assertEqual(login.call_count, 1)
        self.assertEqual(logout.call_count, 1)

    def test_errors(self):
        stack = Stack(username='foo', password='bar', hostname='stack.example.com')
        stack.http = MagicMock()
        stack.http.post.return_value = self.resp('An error occurred')

        with self.assertRaises(StackException):
            stack.login()

        stack._Stack__logged_in = True

        stack.http.get.return_value = self.resp('Insufficient privileges', status=403)

        with self.assertRaises(StackException):
            list(stack.users)

        with self.assertRaises(StackException):
            list(stack.walk(order='foo'))

        with self.assertRaises(StackException):
            list(stack.ls(order='foo'))

    def test_remaining_props(self):
        """Unfortunately there's no way to have two admin accounts, we'll have to mock it instead."""

        users = {
            "amountUsers": 1,
            "diskInfo": {
                "size": 1101659111424,
                "free": 1060504558592,
                "inUse": 41154552832
            },
            "users": [
                {
                    "username": "example",
                    "displayName": "Example",
                    "quota": -1,
                    "used": 1466632,
                    "isAdmin": False,
                    "isPremium": False,
                    "isSFTPEnabled": False,
                    "language": "nl_NL"
                }
            ]
        }

        no_users = users.copy()
        no_users['users'] = []

        stack = Stack(username='foo', password='bar', hostname='stack.example.com')
        stack.http = MagicMock()
        stack.http.get.return_value = self.resp(data=users, is_json=True)

        for user in stack.users:
            self.assertIsInstance(user, StackUser)
            self.assertEqual(user.name, "Example")
            self.assertEqual(user.username, "example")

        user = stack.user('example')
        self.assertIsNone(user.disk_quota)
        self.assertEqual(user.disk_used, 1466632)
        self.assertEqual(user.language, "nl_NL")
        self.assertFalse(user.is_premium)
        self.assertFalse(user.is_admin)

        self.assertEqual(user.username, 'example')
        user.username = 'foo'
        self.assertEqual(user.username, 'foo')

        self.assertEqual(user.name, 'Example')
        user.name = 'Foo'
        self.assertEqual(user.name, 'Foo')

        user.language = 'en_US'
        user.disk_quota = 200000

        stack.http.post.return_value = self.resp({'status': 'ok'}, is_json=True)
        user.save()

        user.delete()

        with self.assertRaises(StackException):
            stack.http.post.return_value = self.resp({'status': 'not ok'}, is_json=True)
            user.delete()

        with self.assertRaises(StackException):
            stack.http.status_code = 200
            stack.http.post.return_value = self.resp({'status': 'not ok'}, is_json=True)
            user.save()

        with self.assertRaises(StackException):
            stack.http.get.return_value = self.resp(no_users, is_json=True)
            stack.user('foo')

        with self.assertRaises(StackException):
            stack.http.get.return_value = self.resp('', status=403)
            stack.user('foo')

        with self.assertRaises(StackException):
            stack.http.post.return_value = self.resp('', status=409)
            stack.create_user(
                name='John Doe',
                username='foo',
                password='bar',
                disk_quota=None)

        with self.assertRaises(StackException):
            stack.http.post.return_value = self.resp({'status': 'not'}, is_json=True)
            stack.create_user(
                name='John Doe',
                username='foo',
                password='bar',
                disk_quota=None)

        stack.http.post.return_value = self.resp({'status': 'ok'}, is_json=True)
        stack.http.get.return_value = self.resp(users, is_json=True)
        stack.create_user(
            name='John Doe',
            username='foo',
            password='bar',
            disk_quota=None)

        with self.assertRaises(StackException):
            stack.enforce_password_policy = True
            stack.create_user(
                name='John Doe',
                username='foo',
                password='bar',
                disk_quota=None)

        stack.http.get.side_effect = (
            self.resp(no_users, is_json=True),
            self.resp(users, is_json=True))

        stack.http.post.return_value = self.resp({'status': 'ok'}, is_json=True)
        stack.user_or_create_new(
            name='John Doe',
            username='foo',
            password='password',
            disk_quota=None)

    def test_live_system(self):
        with Stack(
            username=self.USERNAME,
            password=self.PASSWORD,
            hostname=self.HOSTNAME
        ) as stack:
            self.assertTrue(stack.authenticated)

            self.assertIsNotNone(stack.http.base_url)

            self.assertEqual(stack.cwd, '/')
            self.assertEqual(stack.pwd, '/')

            stack.mkdir(self.PREFIX)
            stack.cd(self.PREFIX)

            for node in stack.walk():
                node.delete()

            self.assertIsInstance(stack.mkdir('foo'), StackDirectory)
            self.assertIsInstance(stack.cd('foo'), StackDirectory)
            self.assertEqual(stack.cwd, '/' + self.PREFIX + '/foo/')

            self.assertIsInstance(stack.mkdir('bar'), StackDirectory)
            self.assertIsInstance(stack.cd('bar'), StackDirectory)
            self.assertEqual(stack.cwd, '/' + self.PREFIX + '/foo/bar/')

            with self.assertRaises(StackException):
                with patch.object(stack.webdav, 'mkdir', side_effect=WebDavException):
                    stack.mkdir('baz')

            stack.cd('/' + self.PREFIX + '/foo/bar/')
            self.assertEqual(stack.cwd, '/' + self.PREFIX + '/foo/bar/')

            with self.assertRaises(StackException, msg='Expected error: /foo/bar/foo does not exist'):
                stack.cd('foo')

            file = BytesIO(b'Hello world')
            file.seek(0)

            result = stack.upload(file, name='hello.txt')
            self.assertIsInstance(result, StackFile)
            self.assertEqual(result.directory, '/' + self.PREFIX + '/foo/bar/')
            self.assertEqual(result.path, '/' + self.PREFIX + '/foo/bar/hello.txt')
            self.assertEqual(result.name, 'hello.txt')
            self.assertEqual(result.type, 'application/text')
            self.assertEqual(result.size, len('Hello world'))
            self.assertEqual(result.exists, True)
            self.assertEqual(result.is_shared, False)
            self.assertEqual(result.has_share_password, False)
            self.assertEqual(result.share_url, None)
            self.assertEqual(result.share_token, None)

            result.share(password='example', expiry_date=datetime.now() + timedelta(days=1))
            self.assertEqual(result.is_shared, True)
            self.assertEqual(result.has_share_password, True)
            self.assertIsNotNone(result.share_url)
            self.assertIsNotNone(result.shared_on)
            self.assertIsNotNone(result.share_token)
            self.assertIsNotNone(result.share_expiry_date)

            result.unshare()

            result.share()
            self.assertEqual(result.is_shared, True)
            self.assertEqual(result.has_share_password, False)
            self.assertIsNotNone(result.share_url)
            self.assertIsNotNone(result.shared_on)
            self.assertIsNotNone(result.share_token)
            self.assertIsNone(result.share_expiry_date)

            result.favorite()
            self.assertTrue(result.is_favorited)

            result.unfavorite()
            self.assertFalse(result.is_favorited)

            with TemporaryDirectory(suffix='transip_stack') as directory:
                output = join(directory, 'foo.txt')
                stack.download('hello.txt', output_path=output)

                with self.assertRaises(StackException):
                    with patch.object(result._webdav, 'download', side_effect=WebDavException):
                        stack.download('hello.txt', output_path=output)

                with self.assertRaises(StackException):
                    with patch.object(result._webdav, 'download_to', side_effect=WebDavException):
                        stack.download_into('hello.txt')

                with open(output) as fd:
                    self.assertEqual(fd.read(), 'Hello world')

                stack.upload(join(directory, 'foo.txt'), name='foo.txt')

                with self.assertRaises(StackException):
                    with patch.object(result._webdav, 'upload_from', side_effect=WebDavException):
                        stack.upload(join(directory, 'foo.txt'), name='foo.txt')

                with self.assertRaises(StackException):
                    stack.upload(BytesIO(b'Hello world'))

            buff = stack.download_into('hello.txt')
            self.assertEqual(buff.read(), b'Hello world')

            with self.assertRaises(StackException):
                # noinspection PyTypeChecker
                stack.download_into('hello.txt', buffer='FooBar')

            self.assertEqual(len(list(stack.ls())), 2)

            result.move('./world.txt')
            self.assertEqual(result.name, 'world.txt')
            self.assertEqual(result.path, '/' + self.PREFIX + '/foo/bar/world.txt')
            self.assertEqual(result.directory, '/' + self.PREFIX + '/foo/bar/')

            result.move('world.txt')
            self.assertEqual(result.name, 'world.txt')
            self.assertEqual(result.path, '/' + self.PREFIX + '/foo/bar/world.txt')
            self.assertEqual(result.directory, '/' + self.PREFIX + '/foo/bar/')

            result.move('../')
            self.assertEqual(result.name, 'world.txt')
            self.assertEqual(result.path, '/' + self.PREFIX + '/foo/world.txt')
            self.assertEqual(result.directory, '/' + self.PREFIX + '/foo/')

            result.move('../example.txt')
            self.assertEqual(result.name, 'example.txt')
            self.assertEqual(result.path, '/' + self.PREFIX + '/example.txt')
            self.assertEqual(result.directory, '/' + self.PREFIX + '/')

            with self.assertRaises(StackException):
                with patch.object(result._webdav, 'move', side_effect=WebDavException):
                    result.move('foo.txt')

            stack.cd('/' + self.PREFIX + '/')
            self.assertEqual(len(list(stack.files)), 1)
            self.assertEqual(len(list(stack.directories)), 1)

            root = stack.directory('/' + self.PREFIX + '/')
            self.assertEqual(root.directory, '/' + self.PREFIX + '/')

            with self.assertRaises(StackException):
                stack.file('foo')

            with self.assertRaises(StackException):
                stack.directory('example.txt')

            with self.assertRaises(StackException):
                stack.upload(None)

            for node in stack.walk():
                node.delete()

    def resp(self, data, status=200, is_json=False):
        """Helper function to create requests responses for mocking"""
        resp = Response()
        resp.status_code = status

        if is_json:
            resp._content = json.dumps(data).encode()
            resp.headers['Content-Type'] = 'application/json'
        else:
            resp._content = data.encode()
            resp.headers['Content-Type'] = 'text/html'

        return resp
