import os
import re
import sys
import socket
import argparse
import time
from exceptions import *

PASSIVE = False
UNITS = ['B/s', 'KB/s', 'MB/s', 'GB/s']
WELCOME = '''
 _      _____ _     ____  ____  _      _____
/ \  /|/  __// \   /   _\/  _ \/ \__/|/  __/
| |  |||  \  | |   |  /  | / \|| |\/|||  \  
| |/\|||  /_ | |_/\|  \_ | \_/|| |  |||  /_ 
\_/  \|\____\\\\____/\____/\____/\_/  \|\____\\
                                            '''
BYE = '''
_________________________▄▀▄_____▄▀▄
________________________▄█░░▀▀▀▀▀░░█▄
____________________▄▄__█░░░░░░░░░░░█__▄▄
___________________█▄▄█_█░░▀░░┬░░▀░░█_█▄▄█
 .----------------.  .----------------.  .----------------. 
| .--------------. || .--------------. || .--------------. |
| |   ______     | || |  ____  ____  | || |  _________   | |
| |  |_   _ \    | || | |_  _||_  _| | || | |_   ___  |  | |
| |    | |_) |   | || |   \ \  / /   | || |   | |_  \_|  | |
| |    |  __'.   | || |    \ \/ /    | || |   |  _|  _   | |
| |   _| |__) |  | || |    _|  |_    | || |  _| |___/ |  | |
| |  |_______/   | || |   |______|   | || | |_________|  | |
| |              | || |              | || |              | |
| '--------------' || '--------------' || '--------------' |
 '----------------'  '----------------'  '----------------' '''

if sys.version_info < (3, 4):
    print('Use python >= 3.4', file=sys.stderr)
    sys.exit()

__version__ = '2.0'
__author__ = 'Iljushchenko Anastasia'


def parse_data():
    parser = argparse.ArgumentParser(prog='FTPclient.py',
                                     description='''FTP-client connects to FTP server''',
                                     epilog='Author: {}'.format(__author__))
    parser.add_argument('address', help='Address to connect with FTP server')
    parser.add_argument('port', help='Connection port', nargs='?', type=int, default=21)
    parser.add_argument('-l', metavar='name', default='anonymous',
                        help='Your username')
    parser.add_argument('-p', metavar='password', default='example@mail.com',
                        help='Your password')
    parser.add_argument('--passive', help='Use passive mode instead of active', action='store_true')
    parser.add_argument('-version', action='version', version=__version__,
                        help='Help you to find out the version of program')
    # group = parser.add_mutually_exclusive_group()
    # group.add_argument('-d', metavar='download', help='Download file')
    # group.add_argument('-u', metavar='upload', help='Upload your file')
    # print(vars(parser.parse_args()))
    return parser.parse_args()


def run(control_sock, data_sock):
    while True:
        try:
            message = input('>>')
            query = message.split(' ')
            command = query[0].lower()
            argument = query[1] if len(query) > 1 else None
            option = query[2] if len(query) > 2 else None
            comm = FUNCTIONS.get(command, invalid)
            result = comm(control_sock, data_sock, argument, option)
            if result is not None and result is socket:
                data_sock = result
        except ConnectionError as error:
            raise error
        except Exception as error:
            print(error)


def login(control_sock, name, passw):
    if name is None:
        name = input('Enter your username: ')
    control_sock.sendall(bytes('USER {}\r\n'.format(name), 'ASCII'))
    receive_answer(control_sock)
    # print(reply)
    if passw is None:
        passw = input('Enter your password: ')
    control_sock.sendall(bytes('PASS {}\r\n'.format(passw), 'ASCII'))
    reply = receive_answer(control_sock)
    # print(reply)
    if not re.match(r'2\d\d', reply):
        raise ValueError('Login is incorrect. '
                         'Sorry but you cannot work with me :( Try again')


def receive_answer(sock):
    reply = ''
    tmp = sock.recv(65535).decode('ASCII')
    reply += tmp
    ans_reg = re.compile(r'^\d\d\d .*$', re.MULTILINE)
    while not re.findall(ans_reg, tmp):
        try:
            tmp = sock.recv(65535).decode('ASCII')
            reply += tmp
        except TimeoutError:
            break
        except Exception as error:
            print(error)
            break
    return reply


def receive_full_data(sock):
    reply = b''
    sock.settimeout(2)
    while True:
        try:
            tmp = sock.recv(65535)
            if not tmp:
                break
        except TimeoutError:
            break
        finally:
            reply += tmp
            return reply


def get(control_sock, data_sock, file_to_load, local_file):
    if file_to_load is None:
        raise ValueError("You don\'t specify remote file name")
    if local_file is None:
        local_file = '{}\{}'.format(os.getcwd(), os.path.basename(file_to_load))
    switch_type(control_sock, None, 'I', None)

    file_size = size(control_sock, None, file_to_load, None)
    if not PASSIVE:
        sock = port(control_sock)
    else:
        data_sock = pasv(control_sock)
    send(control_sock, 'RETR', file_to_load)
    reply = receive_answer(control_sock)
    # print(reply)

    if not reply.startswith('150'):
        raise FileNotFoundError('Couldn\'t download file {}'.format(file_to_load))
    if not PASSIVE:
        data_sock, address = sock.accept()
    with open(local_file, 'wb') as result:
        received = 0
        start_time = time.time()
        while file_size > received:
            data = data_sock.recv(65535)
            if not data:
                break
            result.write(data)
            received += len(data)
            print_progress(received, file_size, start_time, time.time())
    data_sock.close()
    reply = receive_answer(control_sock)
    print(reply)


def put(control_sock, data_sock, local_file, remote_name):
    if local_file is None:
        raise ValueError("Please specify local file name")
    if remote_name is None:
        remote_name = os.path.basename(local_file)
    switch_type(control_sock, None, 'I', None)
    if not PASSIVE:
        sock = port(control_sock)
    else:
        data_sock = pasv(control_sock)
    send(control_sock, 'STOR', remote_name)
    reply = receive_answer(control_sock)
    # print(reply)
    if reply[0] == '5':
        print('You have no permission to store the file. Please, relogin')
        return
    if not PASSIVE:
        data_sock, address = sock.accept()
    with open(local_file, 'rb') as file:
        sent = 0
        file_size = os.path.getsize(local_file)
        start_time = time.time()
        while file_size > sent:
            data = file.read(65535)
            data_sock.sendall(data)
            sent += len(data)
            print_progress(sent, file_size, start_time, time.time())
    data_sock.close()
    reply = receive_answer(control_sock)
    print(reply)


def pasv(control_sock, data_sock=None, argument=None, extra_arg=None):
    send(control_sock, 'PASV')
    reply = receive_answer(control_sock)
    print(reply)
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
        print(error)
    except Exception as error:
        print(error)
    PASSIVE = True
    return data_sock


def port(control_sock, data_sock=None, argument=None, extra_argument=None):
    # socket’s own address
    ip_address = control_sock.getsockname()[0]
    sock = socket.socket()
    sock.bind(('', 0))
    sock.listen()
    local_port = sock.getsockname()[1]
    port_int, port_modulo = local_port // 256, local_port % 256
    query = 'PORT {},{},{}'.format(ip_address.replace('.', ','), port_int, port_modulo)
    send(control_sock, query)
    reply = receive_answer(control_sock)
    print(reply)
    if not reply.startswith('2'):
        print('Active mode is not available. Try passive')
    return sock


def dir_list(control_sock, data_sock=None, argument=None, extra_arg=None):
    if not PASSIVE:
        sock = port(control_sock)
    else:
        data_sock = pasv(control_sock)
    send(control_sock, 'LIST')
    reply = receive_answer(control_sock)
    print(reply)
    if not PASSIVE:
        data_sock, address = sock.accept()
    if data_sock is None:
        raise ConnectionError('Data connection is required')
    data = receive_full_data(data_sock).decode('UTF-8')
    print(data)
    data_sock.close()
    reply = receive_answer(control_sock)
    print(reply)  # 226 Transfer complete
    if argument is not None and argument.lower() == '-r':
        reg = re.compile(r' (\.|\w+)+?\r\n')
        result = re.findall(reg, data)
        for folder in result:
            try:
                cwd(control_sock, data_sock, folder, True)
            except NotChangedDirectoryError as e:
                continue
            pwd(control_sock, data_sock, True, None)
            dir_list(control_sock, data_sock, '-r', None)
        curr_folder = pwd(control_sock, data_sock, True, None)
        dir = re.findall(r'\"(.+)\"', curr_folder)[0].split('/')
        new_dir = '/'.join(dir[:len(dir) - 1])
        cwd(control_sock, None, '/' + new_dir, True)


def convert_speed(speed):
    unit_index = 0
    while speed > 1024:
        speed /= 1024
        unit_index += 1
    return '{:.1f}{}'.format(speed, UNITS[unit_index])


def print_progress(done, total, start_time, current):
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
                             convert_speed(speed),
                             expected_time))
    if done == total:
        sys.stdout.write('\n\n')
    sys.stdout.flush()


def send(sock, command, argument=None):
    if argument is not None:
        query = '{} {}\r\n'.format(command, argument)
    else:
        query = '{}\r\n'.format(command)
    sock.sendall(bytes(query, 'ASCII'))


def size(control_sock, data_sock, filename, path_value):
    if filename is None:
        raise ValueError('You don\'t specify file name')
    send(control_sock, 'SIZE', filename)
    reply = receive_answer(control_sock)
    reg = r' (\d+)'
    result = re.findall(reg, reply)
    return int(result[0])


"""
def print_size(control_sock, data_sock, filename, path_value):
    number = size(control_sock, data_sock, filename, path_value)
    print('The size of \'{}\' is {}'.format(filename, number))
"""


def switch_type(control_sock, data_sock, name, extra_arg):
    send(control_sock, 'TYPE', name)
    reply = receive_answer(control_sock)
    # print(reply)


def connect(address, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    try:
        address = socket.getaddrinfo(address, port)
        sock.connect(address[0][4])
    except socket.gaierror as error:
        raise ConnectionError('Address fetching failed: {}:{}'.format(address, port))
    except Exception as error:
        raise ConnectionError('Connection error: ' + str(error))
    return sock


def disconnect(control_sock, data_sock=None, argument=None, extra_arg=None):
    send(control_sock, 'QUIT')
    reply = receive_answer(control_sock)
    # print(reply)
    # print('See ya next time :)')
    print(BYE)
    sys.exit(0)


def main():
    args = parse_data()
    if args.passive:
        global PASSIVE
        PASSIVE = True
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10)
    print('Connecting to {}:{}'.format(args.address, args.port))
    # Присоединяемся к серверу
    sock.connect((args.address, args.port))
    reply = receive_answer(sock)
    print(reply)
    try:
        data_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        data_sock.connect((args.address, args.port))
        login(sock, args.l, args.p)
    except ConnectionError as error:
        print('Connection failed')
        sys.exit(1)
    except Exception as error:
        print(error)
        disconnect(sock)
    print('The login with username \"' + args.l + '\" was successful')
    print(WELCOME)
    print('Print \"?\" to show available commands')
    run(sock, data_sock)
    '''
    data_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    data_sock.connect((args.address, args.port))
    data = b''
    with open('downloaded', 'wb') as result:
        data = data_sock.recv(1024)
        while data:
            result.write(data)
            # Читаем данные от сервера, но не более 1024 байт
            data = data_sock.recv(1024)
    # Закрываем соединение
    data_sock.close()
    sock.close()
'''


def cwd(control_sock, data_sock, path, extra_arg):
    send(control_sock, 'CWD', path)
    reply = receive_answer(control_sock)
    if not reply.startswith('2'):
        raise NotChangedDirectoryError('Cannot change directory')


def pwd(control_sock, data_sock, not_print, extra_arg):
    send(control_sock, 'PWD')
    reply = receive_answer(control_sock)
    if not not_print:
        print(reply)
    else:
        return reply


def invalid(arg1, arg2, arg3, arg4):
    print('Invalid command\nUse "HELP" command or "?" for internal help')


def server_help(control_sock, data_sock, argument, extra_arg):
    send(control_sock, 'HELP')
    reply = receive_answer(control_sock)
    print(reply)


def int_help(arg1, arg2, arg3, arg4):
    print("""Supported commands:
    Command\tUsing\t\tDescription\t 
    user\tuser $username\tRelogin\t
    quit\tquit\t\tClose FTP-client\t
    help\thelp\t\tSend help request to server\t
    ls\t\tls\t\tShow current directory\t
    cd\t\tcd $new_dir\tChange working directory
    pwd\t\tpwd\t\tPrint working directory
    size\tsize $filename\tFind file size\t
    get\t\tget $filename\tDownload file\t
    put\t\tput $filename\tSave file (if it is available) 
    pasv\tpasv\t\tChange mode to the passive
    type\ttype $type\tChange data send mode
    ?\t\t\t\tShow this help message\t
    """)


FUNCTIONS = {
    'user': login,
    'quit': disconnect,
    'help': server_help,
    'size': size,
    'ls': dir_list,
    'cd': cwd,
    'pwd': pwd,
    'get': get,
    'put': put,
    'type': switch_type,
    'port': port,
    'pasv': pasv,
    '?': int_help
}


if __name__ == '__main__':
    main()
    sys.exit(0)
