from enum import StrEnum


class PowerState(StrEnum):
    ON = "on"
    OFF = "off"
    UNKNOWN = "unknown"
    ERROR = "error"
