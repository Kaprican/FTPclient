from unittest import mock

from stubserver import FTPStubServer
from Client import FTP, parse_data, get, upload
import tempfile
import unittest
from exceptions import *


class FTPclientTest(unittest.TestCase):

    def setUp(self):
        self.server = FTPStubServer(0)
        self.server.run()
        self.port = self.server.server.server_address[1]
        self.ftp = FTP(True)
        self.ftp.connect('localhost', self.port)

    def tearDown(self):
        self.ftp.disconnect()
        self.server.stop()
        # implicitly calls verify on stop

    def test_directories(self):
        folder = 'some_dir'
        expected = '257 "' + folder + '" is your current location\r\n'
        self.ftp.cwd(None, folder)
        curr_dir = self.ftp.pwd()
        self.assertEqual(curr_dir, expected)

    def test_get(self):
        file = "image.png"
        self.server.add_file(file, 'asd')
        temp = tempfile.NamedTemporaryFile(delete=False)
        with mock.patch.object(self.ftp, 'size', return_value=5):
            self.ftp.get(None, file, temp.name)
        with open(temp.name, 'r') as file:
            data = file.read()
        self.assertEqual(data, "asd")
        temp.close()

    def test_list(self):
        first = "first.txt"
        second = "second.txt"
        self.server.add_file(first, 'Some string')
        self.server.add_file(second, 'Another string. It is bigger')
        listing = self.ftp.dir_list().split('\n')
        dir = set(filter(None, listing))
        self.assertEqual(dir, {first, second})

    def test_pasv(self):
        data_sock = self.ftp.pasv()
        self.assertTrue(data_sock)

    def test_type_A(self):
        self.ftp.switch_type(type="A")
        self.assertFalse(self.ftp.binary)

    def test_type_I(self):
        self.ftp.switch_type(type="I")
        self.assertTrue(self.ftp.binary)

    def test_no_type(self):
        with self.assertRaises(NoTypeException):
            self.ftp.switch_type()


class FTPParserTest(unittest.TestCase):

    def test_simple(self):
        data = vars(parse_data(['127.0.0.1 21']))
        exp = {'address': '127.0.0.1 21',
               'l': 'anonymous',
               'port': 21,
               'p': 'example@mail.com',
               'passive': False,
               'get': None,
               'upload': None}
        self.assertTrue(data == exp)

    def test_simple_port(self):
        data = vars(parse_data(['127.0.0.1 21', '25']))
        exp = {'address': '127.0.0.1 21',
               'l': 'anonymous',
               'port': 25,
               'p': 'example@mail.com',
               'passive': False,
               'get': None,
               'upload': None}
        self.assertTrue(data == exp)

    def test_passive(self):
        data = vars(parse_data(['127.0.0.1 21', '-passive']))
        exp = {'address': '127.0.0.1 21',
               'l': 'anonymous',
               'port': 21,
               'p': 'example@mail.com',
               'passive': True,
               'get': None,
               'upload': None}
        self.assertTrue(data == exp)

    def test_get(self):
        data = vars(parse_data(['127.0.0.1 21', '-get', 'flp/readme.txt', 'current']))
        exp = {'address': '127.0.0.1 21',
               'l': 'anonymous',
               'port': 21,
               'p': 'example@mail.com',
               'passive': False,
               'get': ['flp/readme.txt', 'current'],
               'upload': None}
        self.assertTrue(data == exp)

    def test_upload(self):
        data = vars(parse_data(['127.0.0.1 21', '-upload', 'flp/readme.txt', 'current']))
        exp = {'address': '127.0.0.1 21',
               'l': 'anonymous',
               'port': 21,
               'p': 'example@mail.com',
               'passive': False,
               'get': None,
               'upload': ['flp/readme.txt', 'current']}
        self.assertTrue(data == exp)


if __name__ == '__main__':
    unittest.main()
