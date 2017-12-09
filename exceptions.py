class NotChangedDirectoryError(Exception):
    pass


class PortNotAllowedError(Exception):
    pass


class WrongTypeException(Exception):
    pass


class NoTypeException(WrongTypeException):
    pass


class LoginException(Exception):
    pass


class WrongDirectoryException(Exception):
    pass
