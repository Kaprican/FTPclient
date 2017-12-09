#!/usr/bin/python3
# -*- coding: utf8 -*-

from unittest import mock
from Client import FTP, parse_data, get, upload, parse_params
import tempfile
import unittest
import sys
import exceptions


try:
    from stubserver import FTPStubServer
except Exception as e:
    print('Module stubserver not found', file=sys.stderr)
    print('Install stubserver')
    sys.exit()


class FTPclientTest(unittest.TestCase):

    @staticmethod
    def dummy(a1, a2, a3, a4):
        pass

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
        self.ftp.change_dir(None, folder)
        curr_dir = self.ftp.current_dir()
        self.assertEqual(curr_dir, expected)

    def test_get(self):
        file = "image.png"
        self.server.add_file(file, 'asd')
        temp = tempfile.NamedTemporaryFile(delete=False)
        with mock.patch.object(self.ftp, 'size', return_value=5):
            self.ftp.get(None, file, temp.name, self.dummy)
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
        with self.assertRaises(exceptions.NoTypeException):
            self.ftp.switch_type()


class FTPParserTest(unittest.TestCase):

    def test_simple(self):
        data = vars(parse_data(['127.0.0.1 21']))
        exp = {'address': '127.0.0.1 21',
               'l': ('ftp', 'ftp'),
               'port': 21,
               'passive': False,
               'get': None,
               'upload': None}
        self.assertTrue(data == exp)

    def test_simple_port(self):
        data = vars(parse_data(['127.0.0.1 21', '25']))
        exp = {'address': '127.0.0.1 21',
               'l': ('ftp', 'ftp'),
               'port': 25,
               'passive': False,
               'get': None,
               'upload': None}
        self.assertTrue(data == exp)

    def test_passive(self):
        data = vars(parse_data(['127.0.0.1 21', '-passive']))
        exp = {'address': '127.0.0.1 21',
               'l': ('ftp', 'ftp'),
               'port': 21,
               'passive': True,
               'get': None,
               'upload': None}
        self.assertTrue(data == exp)

    def test_get(self):
        data = vars(parse_data(['127.0.0.1 21', '-get', 'flp/readme.txt', 'current']))
        exp = {'address': '127.0.0.1 21',
               'l': ('ftp', 'ftp'),
               'port': 21,
               'passive': False,
               'get': ['flp/readme.txt', 'current'],
               'upload': None}
        self.assertTrue(data == exp)

    def test_upload(self):
        data = vars(parse_data(['127.0.0.1 21', '-upload', 'flp/readme.txt', 'current']))
        exp = {'address': '127.0.0.1 21',
               'l': ('ftp', 'ftp'),
               'port': 21,
               'passive': False,
               'get': None,
               'upload': ['flp/readme.txt', 'current']}
        self.assertTrue(data == exp)


class FTPClientTest(unittest.TestCase):

    def test_parse_params1(self):
        data = parse_params(r'get "Два мегабайта.txt" "C:\Users\nasty\OneDrive\Documents\Новая папка\\"')
        exp = ["get", "Два мегабайта.txt", r"C:\Users\nasty\OneDrive\Documents\Новая папка" + "\\"]
        self.assertTrue(data == exp)

    def test_parse_params4(self):
        data = parse_params(r'get f1.txt "C:\Users\nasty\OneDrive\Documents\Новая папка\\"')
        exp = ["get", "f1.txt", r"C:\Users\nasty\OneDrive\Documents\Новая папка" + "\\"]
        self.assertTrue(data == exp)


if __name__ == '__main__':
    unittest.main()
