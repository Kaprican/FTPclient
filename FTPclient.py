import os
import sys
import argparse
import socket
import re

if sys.version_info < (3, 4):
    print('Use python >= 3.4', file=sys.stderr)
    sys.exit()

__version__ = '1.0'
__author__ = 'Iljushchenko Anastasia'
FILE_TRANSFER_START = '150'


def parse_data():
    parser = argparse.ArgumentParser(prog='FTPclient.py',
                                     description='''FTP-client connects to FTP server''',
                                     epilog='Author: {}'.format(__author__))
    parser.add_argument('address', help='Address to connect with FTP server')
    parser.add_argument('port', help='Connection port', nargs='?', type=int, default=21)
    # parser.add_argument('--passive',
    # help='Use passive mode instead of active', action='store_true')
    parser.add_argument('-l', '-login', metavar='name', default='anonymous',
                        help='Your username (\'anonymous\' by default)')
    parser.add_argument('-p', '-password', metavar='passwd', default='example@mail.com',
                        help='Your password (example@mail.com by default)')
    parser.add_argument('--version', action='version', version=__version__,
                        help='Help you to find out the version of program')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-d', metavar='get', help='Download your file')
    group.add_argument('-u', metavar='put', help='Upload your file')
    return parser.parse_args()


def connect(host):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    try:
        address = socket.getaddrinfo(host[0], host[1])
        sock.connect(address[0][4])
    except socket.gaierror:
        raise ConnectionError('Address fetching failed: {}:{}'.format(host[0], host[1]))
    except Exception as error:
        raise ConnectionError('Connection error: ' + str(error))
    return sock


def main():
    args = parse_data()
    address = (args.address, args.port)
    print('Connecting to {} : {}'.format(address[0], address[1]))
    sock = socket.socket()
    # вызовет исключение,
    # если значение периода тайм-аута истекло до завершения операции
    sock.settimeout(2) # сделать возможность настройки
    data_sock = socket.socket()
    try:
        sock = connect(address)
        print(receive_answer(sock))
        data_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        data_sock.settimeout(2)
        data_sock.close()
        if args.get:
            try:
                login(sock, data_sock, 'anonymous', 'ftp')
                get(sock, data_sock, args.remote, args.local)
            except Exception as error:
                print(error)
            finally:
                disconnect(sock)
        login(sock, None, args.name, args.passwd)
        run(sock, data_sock)
    except ConnectionError as error:
        print(error)
        sys.exit(1)
    except Exception as error:
        print(error)
        run(sock, data_sock)


def run(control_sock, data_sock):
    while True:
        try:
            message = input('>')
            query = message.split(' ')
            command = query[0].lower()
            argument = query[1] if len(query) > 1 else None
            option = query[2] if len(query) > 2 else None
            comm = FUNCTIONS.get(command, invalid)
            result = comm(control_sock, data_sock, argument, option)
            if result is not None:
                data_sock = result
        except ConnectionError as error:
            raise error
        except Exception as error:
            print(error)


def get(control_sock, data_sock, downloaded_file, local_file):
    if downloaded_file is None:
        raise ValueError("Please specify remote file name")
    if local_file is None:
        local_file = '{}/{}'.format(os.getcwd(), os.path.basename(downloaded_file))
    sock = port(control_sock)
    file_size = size(control_sock, None, downloaded_file, None)
    send(control_sock, 'RETR', downloaded_file)
    reply = receive_answer(control_sock)
    print(reply)
    if not reply.startswith(FILE_TRANSFER_START):
        raise FileNotFoundError('Couldn\'t download file {}'.format(downloaded_file))
    data_sock, address = sock.accept()
    with open(local_file, 'wb') as result:
        received = 0
        while file_size > received:
            data = data_sock.recv(65535)
            if not data:
                break
            result.write(data)
            received += len(data)
    data_sock.close()
    reply = receive_answer(control_sock)
    print(reply)


def port(control_sock, data_sock=None, argument=None, extra_argument=None):
    ip_address = control_sock.getsockname()[0]
    sock = socket.socket()
    sock.bind(('', 0))
    sock.listen()
    local_port = sock.getsockname()[1]
    port_whole, port_factor = local_port // 256, local_port % 256
    query = 'PORT {},{},{}'.format(ip_address.replace('.', ','), port_whole, port_factor)
    send(control_sock, query)
    reply = receive_answer(control_sock)
    print(reply)
    return sock


def size(control_sock, data_sock, filename, path_value):
    send(control_sock, 'SIZE', filename)
    reply = receive_answer(control_sock)
    reg = r' (\d+)'
    result = re.findall(reg, reply)
    return int(result[0])


def send(sock, command, arg=None):
    if arg is not None:
        mess = '{} {}\r\n'.format(command, arg)
    else:
        mess = '{}\r\n'.format(command)
    sock.sendall(bytes(mess, 'ASCII'))


def receive_answer(sock):
    reply = ''
    tmp = sock.recv(65535).decode('ASCII') # получает данные из сокета
    reply += tmp
    first_reply_reg = re.compile(r'^\d{3} .*$', re.MULTILINE)
    while not re.findall(first_reply_reg, tmp):
        try:
            tmp = sock.recv(65535).decode('ASCII')
            reply += tmp
        except TimeoutError:
            break
    return reply


def login(control_sock, data_sock, name, passwd):
    if name is None:
        name = input('Username: ')
    send(control_sock, 'USER', name)
    reply = receive_answer(control_sock)
    print(reply)
    password(control_sock, None, passwd, None)


def password(control_sock, data_sock, passw, extra_arg):
    if passw is None:
        passw = input('Password: ')
    send(control_sock, 'PASS', passw)
    reply = receive_answer(control_sock)
    reg = re.compile(r'2\d{2}')
    print(reply)
    if not re.match(reg, reply):
        raise ValueError('Login is incorrect. Sign in with \'user\' command')


def disconnect(control_sock, data_sock=None, argument=None, extra_arg=None):
    send(control_sock, 'QUIT')
    reply = receive_answer(control_sock)
    print(reply)
    sys.exit(0)


def invalid(arg1, arg2, arg3, arg4):
    print('Invalid command\nUse "HELP" command or "/?" for internal help')


def server_help(control_sock, data_sock, argument, extra_arg):
    send(control_sock, 'HELP')
    reply = receive_answer(control_sock)
    print(reply)


def int_help(arg1, arg2, arg3, arg4):
    print("""Supported commands:
    user\tpass\tquit\thelp\t
    size\tget\t?
    """)


FUNCTIONS = {
    'user': login,
    'pass': password,
    'quit': disconnect,
    'help': server_help,
    'size': size,
    'get': get,
    'port': port,
    '?': int_help
}

if __name__ == '__main__':
    main()