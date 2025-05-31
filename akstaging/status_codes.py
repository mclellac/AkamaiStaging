# akstaging/status_codes.py
from enum import Enum


class Status(Enum):
    SUCCESS = 0
    ERROR_PERMISSION = 1
    ERROR_NOT_FOUND = 2
    ERROR_IO = 3
    ERROR_INTERNAL = 4
    USER_CANCELLED = 5
    ALREADY_EXISTS = 6
    ERROR_UNSUPPORTED_FLATPAK = 7
