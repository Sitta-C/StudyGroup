"""Validate the wire envelope, not authentication or feature-specific payloads."""

import math
import re

from shared.message_types import (
    PROTOCOL_VERSION,
    RESPONSE_TYPE,
    ErrorCode,
    EventType,
    RequestType,
)

MAX_JSON_DEPTH = 64
_REQUEST_ID = re.compile(r"[A-Za-z0-9_.:-]{1,64}\Z", re.ASCII)


class ProtocolError(ValueError):
    """Malformed frame/packet. Messages never include the received payload."""

    def __init__(self, code: ErrorCode, message: str):
        self.code = code
        super().__init__(message)


class PacketValidationError(ProtocolError):
    """The JSON value is not a supported version 1 packet."""


def _invalid(message: str, code: ErrorCode = ErrorCode.INVALID_PACKET):
    raise PacketValidationError(code, message)


def _validate_json(value, depth=0, ancestors=None):
    """Reject Python-only values, cycles, non-finite numbers and bad Unicode."""
    if depth > MAX_JSON_DEPTH:
        _invalid("JSON nesting exceeds the supported depth")
    if value is None or type(value) in (bool, int):
        return
    if isinstance(value, str):
        try:
            value.encode("utf-8")
        except UnicodeEncodeError:
            _invalid("JSON strings must contain valid Unicode")
        return
    if type(value) is float:
        if not math.isfinite(value):
            _invalid("JSON numbers must be finite")
        return
    if type(value) not in (dict, list):
        _invalid("Packet contains a value unsupported by JSON")
    if ancestors is None:
        ancestors = set()
    identity = id(value)
    if identity in ancestors:
        _invalid("Packet contains a circular reference")
    ancestors.add(identity)
    try:
        if type(value) is dict:
            for key, item in value.items():
                if not isinstance(key, str):
                    _invalid("JSON object keys must be strings")
                _validate_json(key, depth + 1, ancestors)
                _validate_json(item, depth + 1, ancestors)
        else:
            for item in value:
                _validate_json(item, depth + 1, ancestors)
    finally:
        ancestors.remove(identity)


def validate_request_id(request_id):
    if not isinstance(request_id, str) or not _REQUEST_ID.fullmatch(request_id):
        _invalid("Request id must be 1-64 ASCII letters, digits or _.:-")


def validate_packet(packet):
    """Validate in place without coercing or mutating; return the same dict.

    `data` schemas for requests/events and successful results belong to the
    feature handlers. This boundary validates JSON and the common envelope only.
    """
    _validate_json(packet)
    if type(packet) is not dict:
        _invalid("Packet must be a JSON object")
    if type(packet.get("v")) is not int:
        _invalid("Packet version must be an integer")
    if packet["v"] != PROTOCOL_VERSION:
        _invalid("Unsupported protocol version", ErrorCode.UNSUPPORTED_VERSION)
    kind = packet.get("type")
    if not isinstance(kind, str):
        _invalid("Packet type must be a string")
    if kind not in (*RequestType, *EventType, RESPONSE_TYPE):
        _invalid("Unknown packet type", ErrorCode.UNKNOWN_TYPE)
    is_event = kind in EventType
    expected = {"v", "type", "data"} if is_event else {"v", "id", "type", "data"}
    if set(packet) != expected:
        _invalid("Packet has missing or unexpected fields")
    if not is_event:
        validate_request_id(packet["id"])
    data = packet["data"]
    if type(data) is not dict:
        _invalid("Packet data must be a JSON object")
    if kind == RESPONSE_TYPE:
        if type(data.get("ok")) is not bool:
            _invalid("Response ok must be a boolean")
        if data["ok"]:
            if set(data) != {"ok", "result"} or type(data["result"]) is not dict:
                _invalid("Successful response requires a result object only")
        else:
            if set(data) != {"ok", "error"} or type(data["error"]) is not dict:
                _invalid("Failed response requires an error object only")
            error = data["error"]
            if set(error) != {"code", "message"}:
                _invalid("Error requires code and message only")
            if not isinstance(error["code"], str) or error["code"] not in ErrorCode:
                _invalid("Unknown error code")
            message = error["message"]
            if not isinstance(message, str) or not message.strip() or len(message) > 512:
                _invalid("Error message must be 1-512 characters and nonblank")
    return packet
