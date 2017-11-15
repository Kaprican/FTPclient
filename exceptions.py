class NotChangedDirectoryError(Exception):
    def __init__(self, message):

        # Call the base class constructor with the parameters it needs
        super(NotChangedDirectoryError, self).__init__(message)


class PortNotAllowedError(Exception):
    def __init__(self, message):

        # Call the base class constructor with the parameters it needs
        super(PortNotAllowedError, self).__init__(message)


class EndException(Exception):
    def __init__(self, message):

        # Call the base class constructor with the parameters it needs
        super(EndException, self).__init__(message)


class WrongTypeException(Exception):
    def __init__(self, message):

        # Call the base class constructor with the parameters it needs
        super(WrongTypeException, self).__init__(message)


class NoTypeException(WrongTypeException):
    def __init__(self, message):

        # Call the base class constructor with the parameters it needs
        super(NoTypeException, self).__init__(message)


class LoginException(Exception):
    def __init__(self, message):

        # Call the base class constructor with the parameters it needs
        super(LoginException, self).__init__(message)
