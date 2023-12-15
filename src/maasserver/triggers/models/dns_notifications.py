from re import compile


class NotValidDNSNotificationPayload(Exception):
    """Error raised when the dynamic dns update notification is not valid."""


class DynamicDNSUpdateNotification:
    """
    Postgres drops duplicated notifications fired in the same transaction.
    Since we are in this case for the dns notifications, we have to ensure that our notifications are unique.
    This is why the notification payload is in the format
    <random md5 string> <message>
    """

    # Match MD5 string + white space.
    DYNAMIC_DNS_PREFIX_PATTERN = compile(r"^[0-9a-f]{32}\s*")

    def __init__(self, payload: str):
        self.payload = payload
        # cache the plain message the first time we parse it
        self.decoded_message = None

    def is_valid(self) -> bool:
        """
        Checks if the payload is a valid dynamic dns update message.
        If it's valid, the result is cached.
        """
        if self.decoded_message:
            return True

        match = self.DYNAMIC_DNS_PREFIX_PATTERN.match(self.payload)
        if not match:
            return False

        # Remove the prefix and cache the result
        self.decoded_message = self.payload[len(match.group(0)) :]
        return True

    def get_decoded_message(self) -> str:
        if self.decoded_message:
            return self.decoded_message

        # Check if it's valid and store the decoded message
        if not self.is_valid():
            raise NotValidDNSNotificationPayload(
                "Message '%s' is not a valid dynamic dns update."
                % self.payload
            )

        return self.decoded_message
