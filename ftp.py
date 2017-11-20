# -*- coding: utf8 -*-

import os
import re
import sys
import socket
import time
from exceptions import *

UNITS = ['B/s', 'KB/s', 'MB/s', 'GB/s']


class FTP:

    def run(self, data_sock):
        while not self.closed:
            try:
                message = input('>>')
                query = message.split(' ')
                command = query[0].lower()
                argument = query[1] if len(query) > 1 else None
                option = query[2] if len(query) > 2 else None
                comm = self.FUNCTIONS.get(command, self.invalid)
                result = comm(data_sock, argument, option)
                if result is not None:
                    if result is socket:
                        data_sock = result
                    else:
                        sys.stdout.write(result)
            except ConnectionError as error:
                sys.stdout.write(str(error) + '\n')
                self.disconnect()
                # raise error
            except EndException:
                break
            except PermissionError as error:
                sys.stdout.write(str(error) + '\n')
                self.log_in(None, None, None)
            except Exception as error:
                sys.stdout.write(str(error) + '\n')

    def log_in(self, data_sock, name, passw):
        """Log in on FTP-sever"""
        if name is None:
            name = input('Enter your username: ')
        self.send('USER', name)
        # print(reply)
        if passw is None:
            passw = input('Enter your password: ')
        reply = self.send('PASS', passw)
        # print(reply)
        if not re.match(r'2\d\d', reply):
            raise LoginException('Login is incorrect. Try again')

    def receive_answer(self):
        """Receive server reply"""
        reply = ''
        tmp = self.sock.recv(65535).decode('ASCII', 'ignore')
        reply += tmp
        ans_reg = re.compile(r'^\d\d\d .*$', re.MULTILINE)
        while not re.findall(ans_reg, tmp):
            try:
                tmp = self.sock.recv(65535).decode('ASCII')
                reply += tmp
            except TimeoutError:
                break
            except Exception as error:
                print(error)
                break
        return reply

    @staticmethod
    def receive_full_data(data_sock):
        """Receive data from data_socket"""
        reply = b''
        tmp = b''
        while True:
            try:
                tmp = data_sock.recv(65535)
                if not tmp:
                    break
            except TimeoutError:
                break
            finally:
                reply += tmp
        return reply

    def get(self, data_sock, file_to_load, local_file):
        """Download file"""
        if file_to_load is None:
            raise ValueError("You don\'t specify remote file name")
        if local_file is None:
            local_file = '{}\{}'.format(os.getcwd(),
                                        os.path.basename(file_to_load))
        self.switch_type(data_sock, 'I')

        fsize = self.size(None, file_to_load)
        sock = socket.socket()
        if not self.passive:
            sock = self.port()
        else:
            data_sock = self.pasv()
        reply = self.send('RETR', file_to_load)
        # print(reply)

        if not reply.startswith('150'):
            raise FileNotFoundError('Couldn\'t download file {}'.format
                                    (file_to_load))
        if not self.passive:
            data_sock, address = sock.accept()
        with open(local_file, 'wb') as result:
            received = 0
            start = time.time()
            while fsize > received:
                data = data_sock.recv(65535)
                if not data:
                    break
                result.write(data)
                received += len(data)
                self.print_progress(received, fsize, start, time.time())
        data_sock.close()
        reply = self.receive_answer()
        return reply

    def put(self, data_sock, local_file, remote_name):
        """Upload file to the server"""
        if local_file is None:
            raise ValueError("Please specify local file name")
        if remote_name is None:
            remote_name = os.path.basename(local_file)
        self.switch_type(data_sock, 'I')
        sock = socket.socket()
        if not self.passive:
            sock = self.port()
        else:
            data_sock = self.pasv()
        reply = self.send('STOR', remote_name)
        # print(reply)
        if reply[0] == '5':
            raise PermissionError('You have no permission to store the file. '
                                  'Please, relogin')
        if not self.passive:
            data_sock, address = sock.accept()
        with open(local_file, 'rb') as file:
            sent = 0
            file_size = os.path.getsize(local_file)
            start_time = time.time()
            while file_size > sent:
                data = file.read(65535)
                data_sock.sendall(data)
                sent += len(data)
                self.print_progress(sent, file_size, start_time, time.time())
        data_sock.close()
        return self.receive_answer()

    def pasv(self, data_sock=None, argument=None, extra_arg=None):
        """Switch on passive mode"""
        reply = self.send('PASV')
        # print(reply)
        reg = r'(\d+),(\d+),(\d+),(\d+),(\d+),(\d+)'
        numbs = re.findall(reg, reply)[0]
        if not numbs:
            print('Passive mode is not available now')
            print('Try later')
            sys.exit(0)
        ip_address = '.'.join(numbs[:4])
        port = int(numbs[4]) * 256 + int(numbs[5])
        data_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            data_sock.connect((ip_address, port))
        except ConnectionError as error:
            raise error
        except Exception as error:
            raise error
        self.passive = True
        return data_sock

    def port(self, data_sock=None, argument=None, extra_argument=None):
        """Switch on active mode"""
        # socket’s own address
        ip_address = self.sock.getsockname()[0]
        sock = socket.socket()
        sock.bind(('', 0))
        sock.listen()
        local_port = sock.getsockname()[1]
        port_int, port_modulo = local_port // 256, local_port % 256
        query = 'PORT {},{},{}'.format(ip_address.replace('.', ','),
                                       port_int, port_modulo)
        reply = self.send(query)
        # print(reply)
        if not reply.startswith('2'):
            raise PortNotAllowedError('Active mode is not available')
        return sock

    def dir_list(self, data_sock=None, flag=None, counter=None, dir_list=''):
        """Take list of files and folders of current directory"""
        if not self.passive:
            try:
                sock = self.port()
            except PortNotAllowedError:
                self.passive = True
                data_sock = self.pasv()
        else:
            data_sock = self.pasv()
        reply = self.send('LIST')
        # print(reply)
        if not self.passive:
            data_sock, address = sock.accept()
        if data_sock is None:
            raise ConnectionError('Data connection is required')
        data = self.receive_full_data(data_sock).decode('UTF-8',
                                                        errors='ignore')
        dir_list += data + '\n'
        # print(data)
        data_sock.close()
        reply = self.receive_answer()
        # print(reply)  # 226 Transfer complete
        if flag and flag.lower() == '-r' \
                and (counter is None or int(counter) > 0):
            reg = re.compile(r' (\.|\w+)+?\r\n')
            result = re.findall(reg, data)
            for folder in result:
                try:
                    self.change_dir(data_sock, folder, True)
                except NotChangedDirectoryError as e:
                    continue
                pwd_reply = self.current_dir(data_sock, True, None)
                curr_folder = re.findall(r'\"(.+)\"', pwd_reply)[0]
                dir_list += curr_folder + '\n'
                dir_list = self.dir_list(data_sock, '-r',
                                         int(counter) - 1 if counter else None,
                                         dir_list)
                dir = re.findall(r'\"(.+)\"', pwd_reply)[0].split('/')
                new_dir = '/'.join(dir[:len(dir) - 1])
                self.change_dir(None, '/' + new_dir, True)
        return dir_list

    @staticmethod
    def convert_speed(speed):
        """Convert speed from bit/s to smth easier"""
        unit_index = 0
        while speed > 1024:
            speed /= 1024
            unit_index += 1
        return '{:.1f}{}'.format(speed, UNITS[unit_index])

    def print_progress(self, done, total, start_time, current):
        """Print progress bar to stout"""
        percent = "{0:.1%}".format(done / total)
        filled_length = int(round(done / float(total) * 20))
        bar = '█' * filled_length + '_' * (20 - filled_length)

        speed = done / (current - start_time + 1)
        expected_time = int((total - done) / speed)
        sys.stdout.write('\rProgress: [{}] {} complete; '
                         'speed:{}; '
                         '{} seconds left'
                         .format(bar,
                                 percent,
                                 self.convert_speed(speed),
                                 expected_time))
        if done == total:
            sys.stdout.write('\n\n')
        sys.stdout.flush()

    def send(self, command, argument=None):
        """Send request"""
        if argument is not None:
            query = '{} {}\r\n'.format(command, argument)
        else:
            query = '{}\r\n'.format(command)
        asciidata = query.encode("utf-8", "ignore")
        self.sock.sendall(bytes(asciidata))
        # self.sock.sendall(bytes(query, 'ASCII'))
        return self.receive_answer()

    def size(self, data_sock, filename, path_value=None):
        """Return file size"""
        if filename is None:
            raise ValueError('You don\'t specify file name')
        reply = self.send('SIZE', filename)
        reg = r' (\d+)'
        result = re.findall(reg, reply)
        return int(result[0])

    """
    def print_size(self, control_sock, data_sock, filename, path_value):
        number = self.size(control_sock, data_sock, filename, path_value)
        print('The size of \'{}\' is {}'.format(filename, number))
    """

    def switch_type(self, data_sock=None, type=None, extra_arg=None):
        """Switch type of data on server"""
        if type is None:
            raise NoTypeException('Please specify the type')
        reply = self.send('TYPE', type.upper())
        if not reply.startswith('2'):
            raise WrongTypeException('This data type does not exist')
        self.binary = type == 'I'
        # print(reply)

    def disconnect(self, data_sock=None, argument=None, extra_arg=None):
        """Abort a session"""
        reply = self.send('QUIT')
        self.sock.shutdown(socket.SHUT_RDWR)
        self.sock.close()
        self.closed = True
        # print(reply)

    def connect(self, address, port):
        """Create a control socket"""
        # Присоединяемся к серверу
        self.sock.connect((address, port))
        return self.receive_answer()

    def change_dir(self, data_sock, path, extra_arg=None):
        """Change working directory"""
        reply = self.send('CWD', path)
        if not reply.startswith('2'):
            raise NotChangedDirectoryError('Cannot change directory')

    def current_dir(self, data_sock=None, arg=None, extra_arg=None):
        """Return working directory"""
        reply = self.send('PWD')
        return reply

    def make_dir(self, data_sock=None, folder_name=None, extra_arg=None):
        """Make directory"""
        reply = self.send('MKD', folder_name)
        if not reply.startswith('2'):
            raise NotChangedDirectoryError('Cannot make directory')

    def remove_dir(self, data_sock=None, folder_name=None, extra_arg=None):
        """Remove a directory"""
        reply = self.send('RMD', folder_name)
        if not reply.startswith('2'):
            raise NotChangedDirectoryError('Cannot remove directory')

    def nlst(self, data_sock=None, folder_name=None, extra_arg=None):
        """Returns a list of file names in a specified directory"""
        reply = self.send('NLST')
        return reply

    def rename(self, data_sock=None, old_name=None, new_name=None):
        """Rename file or directory"""
        reply = self.send('RNFR', old_name)
        # print(reply)
        if not reply.startswith('3'):
            return reply
        reply = self.send('RNTO', new_name)
        return reply

    def delete_file(self, data_sock=None, file=None, args=None):
        """Delete file"""
        reply = self.send('DELE', file)
        return reply

    @staticmethod
    def invalid(arg1, arg2, arg3):
        """Print wrong command  message"""
        sys.stdout.write('Invalid command\nUse "?" command for internal help')

    @staticmethod
    def help(arg1, arg2, arg3):
        """Print FTP-client help"""
        print("""Supported commands:
        Command\tUsing\t\tDescription\t
        get\tget $filename\tDownload file\t
        put\tput $filename\tSave file (if it is available)
        quit\tquit\t\tClose FTP-client\t
        ls\tls\t\tShow current directory\t
        \tls -r\t\tShow current and all embedded directories (recursively)
        \tls -r $number\tShow current and embedded directories
        \t\t\t  at $number levels in depth
        cd\tcd $new_dir\tChange working directory
        pwd\tpwd\t\tPrint working directory
        mkd\tmkd $new_dir\tMake directory
        rmd\trmd $dir_name\tRemove directory
        rename\trename $1 $2\tRename file or directory from $1 to $2
        del\tdel $filename\tDelete file
        size\tsize $filename\tFind file size\t
        pasv\tpasv\t\tChange mode to the passive
        user\tuser $username\tRelogin\t
        type\ttype $type\tChange data send mode
        ?\t\t\tShow this help message\t
        """)

    def __init__(self, passive=False):
        """FTP class"""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(5)
        self.passive = passive
        self.binary = False
        self.closed = False

        self.FUNCTIONS = {
            'user': self.log_in,
            'quit': self.disconnect,
            'size': self.size,
            'ls': self.dir_list,
            'cd': self.change_dir,
            'pwd': self.current_dir,
            'rename': self.rename,
            'mkd': self.make_dir,
            'rmd': self.remove_dir,
            'get': self.get,
            'put': self.put,
            'del': self.delete_file,
            'type': self.switch_type,
            'port': self.port,
            'pasv': self.pasv,
            '?': self.help
        }
