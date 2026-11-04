#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass
from datetime import datetime
import hashlib
import hmac
import math
import re
import secrets

PAT_PREFIX = "maas_pat_"
PUBLIC_ID_BYTES = 8
SECRET_BYTES = 32
THROTTLE_MINUTES = 10

_BASE62_ALPHABET = (
    "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
)
# Base62 digits needed to represent SECRET_BYTES bytes; 43 for 32 bytes.
_SECRET_LENGTH = math.ceil(SECRET_BYTES * 8 / math.log2(len(_BASE62_ALPHABET)))
_TOKEN_REGEX = re.compile(
    rf"{PAT_PREFIX}(?P<public_id>[0-9a-f]{{{PUBLIC_ID_BYTES * 2}}})"
    rf"_(?P<secret>[0-9A-Za-z]{{{_SECRET_LENGTH}}})"
)


@dataclass(frozen=True)
class GeneratedApiToken:
    public_id: str
    secret_hash: str
    raw_token: str


def _base62_encode(data: bytes) -> str:
    number = int.from_bytes(data, "big")
    digits = []
    while number:
        number, remainder = divmod(number, 62)
        digits.append(_BASE62_ALPHABET[remainder])
    return "".join(reversed(digits)).rjust(_SECRET_LENGTH, "0")


def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def generate_api_token() -> GeneratedApiToken:
    public_id = secrets.token_hex(PUBLIC_ID_BYTES)
    secret = _base62_encode(secrets.token_bytes(SECRET_BYTES))
    return GeneratedApiToken(
        public_id=public_id,
        secret_hash=hash_secret(secret),
        raw_token=f"{PAT_PREFIX}{public_id}_{secret}",
    )


def parse_api_token(raw_token: str) -> tuple[str, str] | None:
    """Return `(public_id, secret)` or `None` if the format is invalid."""
    match = _TOKEN_REGEX.fullmatch(raw_token)
    if not match:
        return None
    return match["public_id"], match["secret"]


def is_api_token(raw_token: str) -> bool:
    return raw_token.startswith(PAT_PREFIX)


def secret_matches(secret: str, secret_hash: str) -> bool:
    return hmac.compare_digest(hash_secret(secret), secret_hash)


def floor_to_throttle_window(moment: datetime) -> datetime:
    return moment.replace(
        minute=moment.minute - moment.minute % THROTTLE_MINUTES,
        second=0,
        microsecond=0,
    )
