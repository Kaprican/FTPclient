#!/usr/bin/env python3
# -*- coding: utf8 -*-
"""Console FTP-client"""

import shlex
import sys
import socket
import os.path

from exceptions import LoginException, NotChangedDirectoryError,\
    WrongDirectoryException
from ftp import FTP
from argparse import ArgumentParser


if sys.version_info < (3, 4):
    print('Use python >= 3.4', file=sys.stderr)
    sys.exit()

__version__ = '3.2'
__author__ = 'Iljushchenko Anastasia'

WELCOME = '''
 _      _____ _     ____  ____  _      _____
/ \  /|/  __// \   /   _\/  _ \/ \__/|/  __/
| |  |||  \  | |   |  /  | / \|| |\/|||  \\
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


def parse_data(args):
    parser = ArgumentParser(prog='Client.py',
                            description='''Interact with FTP server''',
                            epilog='Author: {}'.format(__author__))
    parser.add_argument('address', help='Address to connect with FTP server')
    parser.add_argument('port', help='Connection port', nargs='?',
                        type=int, default=21)
    parser.add_argument('-l', metavar=('USERNAME', 'PASSWORD'), nargs='*',
                        default=('ftp', 'ftp'),
                        help='Username and password (optionally)')
    parser.add_argument('-passive', help='Use passive mode instead of active',
                        action='store_true')
    parser.add_argument('-version', action='version', version=__version__,
                        help='Help you to find out the version of program')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-get', nargs=2, metavar=('FILE_NAME', 'LOCAL_PATH'),
                       help='Download file (without interactive mode). '
                            'If you want to save file to the current directory write \"current\"')
    group.add_argument('-upload', nargs=2, metavar=('FILE_NAME', 'PATH'),
                       dest='upload', help='Upload your file (without interactive mode)')
    # print(vars(parser.parse_args(args)))
    return parser.parse_args(args)


def main():
    data = parse_data(sys.argv[1:])
    ftp = FTP(data.passive)
    print('Connecting to {}:{}'.format(data.address, data.port))
    reply = ftp.connect(data.address, data.port)
    print(reply)
    data_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        data_sock.connect((data.address, data.port))
        data_sock.close()
        data_login = data.l[0:2]
        print(ftp.log_in(data_sock, *data_login))
    except ConnectionError:
        print('Connection failed')
        sys.exit(1)
    except LoginException:
        ftp.log_in(data_sock, 'anonymous', 'qwerty')
    except Exception as error:
        print(error)
        ftp.disconnect()
    if data.get:
        print(get(ftp, data_sock, data.get[0], data.get[1]))
        ftp.disconnect()
    elif data.upload:
        print(upload(ftp, data_sock, data.upload[0], data.upload[1]))
        ftp.disconnect()
    else:
        print(WELCOME)
        print('Print \"?\" to show available commands')
        run(ftp, data_sock)
        print(BYE)


def run(ftp, data_sock):
    while not ftp.closed:
        message = input('>>')
        query = parse_params(message)
        if query is None:
            continue
        command = query[0].lower()
        argument = query[1] if len(query) > 1 else None
        option = query[2] if len(query) > 2 else None
        comm = ftp.FUNCTIONS.get(command, ftp.invalid)
        try:
            result = comm(data_sock, argument, option, print_progress)
            if result is not None:
                if isinstance(result, socket.socket):
                    data_sock = result
                else:
                    sys.stdout.write(result)
        except ConnectionError as error:
            sys.stdout.write(str(error) + '\n')
            ftp.disconnect()
            # raise error
        except PermissionError as error:
            sys.stdout.write(str(error) + '\n')
            ftp.log_in()
        except Exception as error:
            sys.stdout.write(str(error) + '\n')


def parse_params(message):
    try:
        query = shlex.split(message)
    except ValueError:
        sys.stdout.write('Please add one more \\ at the end of the path' + '\n')
        return None
    except Exception:
        sys.stdout.write('Wrong parameters' + '\n')
        return None
    if len(query) > 3:
        return None
    return query


def print_progress(done, total, start_time, current):
    """Print progress bar to stout"""
    percent = "{0:.1%}".format(done / total)
    filled_length = int(done / float(total) * 20)
    bar = '█' * filled_length + '_' * (20 - filled_length)

    speed = done / (current - start_time + 1)
    expected_time = int((total - done) / speed)
    sys.stdout.write('\r' + ' ' * 90)
    sys.stdout.write('\rProgress: |{}| {} complete; '
                     'speed:{}; '
                     '{} seconds left'
                     .format(bar,
                             percent,
                             convert_speed(speed),
                             expected_time))
    if done == total:
        sys.stdout.write('\n\n')
    sys.stdout.flush()


def convert_speed(speed):
    """Convert speed from bit/s to smth easier"""
    unit_index = 0
    while speed > 1024:
        speed /= 1024
        unit_index += 1
    return '{:.1f}{}'.format(speed, FTP.UNITS[unit_index])


def get(ftp, data_sock, filename, os_path):
    path = os.path.dirname(filename)
    if os_path == 'current':
        os_path = None
    # local_dir = os.path.dirname(os_path)
    file_name = os.path.basename(filename)
    # local_file = os.path.join(local_dir, file_name)
    try:
        ftp.change_dir(data_sock, path)
        return ftp.get(data_sock, file_name, os_path, print_progress)
    except NotChangedDirectoryError:
        return 'Wrong path'
    except FileNotFoundError:
        return 'This file is not exist'
    except WrongDirectoryException:
        return 'Close the path in quotation marks'


def upload(ftp, data_sock, filename, path):
    if not os.path.isfile(filename):
        ftp.disconnect()
        return 'This file is not exist'
    file_name = os.path.basename(filename)
    try:
        ftp.change_dir(data_sock, path)
        return ftp.put(data_sock, file_name, file_name, print_progress)
    except NotChangedDirectoryError:
        return 'Wrong path'
    except ValueError:
        return 'It is not a file'
    except PermissionError as e:
        return e


if __name__ == '__main__':
    main()
    sys.exit(0)
