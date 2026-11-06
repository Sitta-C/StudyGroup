"""CP02 acceptance tests: actual loopback TCP streams, never developer data."""

import copy
import json
import socket
import struct
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from shared.message_types import ErrorCode, EventType, RequestType
from shared.protocol import (
    HEADER,
    MAX_FRAME_BYTES,
    IncompleteFrameError,
    PacketConnection,
    ProtocolError,
    encode_packet,
    make_error,
    make_event,
    make_request,
    make_response,
    recv_exact,
    recv_packet,
)
from shared.validation import MAX_JSON_DEPTH, PacketValidationError, validate_packet


@pytest.fixture
def tcp_pair():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.settimeout(5)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        with socket.create_connection(listener.getsockname(), timeout=5) as sender:
            receiver, _ = listener.accept()
            with receiver:
                receiver.settimeout(5)
                yield sender, receiver


def request():
    return make_request(
        RequestType.MESSAGE_SEND,
        {"room_id": 12, "text": "ประชุมสองทุ่มนะ 👩🏽‍💻\n日本語 café e\u0301"},
        request_id="req-42",
    )


def raw_frame(body):
    if isinstance(body, str):
        body = body.encode("utf-8")
    return HEADER.pack(len(body)) + body


def test_request_response_and_event_over_tcp(tcp_pair):
    left, right = map(PacketConnection, tcp_pair)
    packet = request()
    left.send_packet(packet)
    received = right.recv_packet()
    assert received == packet
    right.send_packet(make_response(received["id"], {"message_id": 205}))
    right.send_packet(make_event(EventType.MESSAGE_NEW, {
        "message_id": 205, "room_id": 12, "sender_id": 3,
        "text": packet["data"]["text"], "created_at": "2026-11-06T13:00:00Z",
    }))
    assert left.recv_packet() == make_response("req-42", {"message_id": 205})
    event = left.recv_packet()
    assert event["type"] == "MESSAGE_NEW"
    assert event["data"]["text"] == packet["data"]["text"]
    assert "id" not in event


def test_error_response_preserves_request_id(tcp_pair):
    sender, receiver = tcp_pair
    error = make_error("req-42", ErrorCode.AUTH_REQUIRED, "กรุณาเข้าสู่ระบบ")
    PacketConnection(sender).send_packet(error)
    assert recv_packet(receiver) == {
        "v": 1, "id": "req-42", "type": "RESPONSE",
        "data": {"ok": False, "error": {
            "code": "AUTH_REQUIRED", "message": "กรุณาเข้าสู่ระบบ",
        }},
    }


def test_header_is_unsigned_big_endian_byte_length():
    frame = encode_packet(request())
    body = frame[4:]
    assert frame[:4] == struct.pack(">I", len(body))
    assert len(body) > len(body.decode("utf-8"))
    assert "ประชุม".encode() in body


class ShortReads:
    """Bound each real recv to force stream fragmentation independent of TCP."""

    def __init__(self, sock, limit):
        self.sock = sock
        self.limit = limit
        self.calls = 0

    def recv(self, size):
        self.calls += 1
        return self.sock.recv(min(size, self.limit))


@pytest.mark.parametrize("limit", [1, 2, 3, 7])
def test_fragmented_header_body_and_multibyte_unicode(tcp_pair, limit):
    sender, receiver = tcp_pair
    frame = encode_packet(request())
    reader = ShortReads(receiver, limit)
    # Fragment the writes as well as the reads, including inside UTF-8 sequences.
    with ThreadPoolExecutor(max_workers=1) as pool:
        def write_fragments():
            for offset in range(0, len(frame), 3):
                sender.sendall(frame[offset:offset + 3])
        writer = pool.submit(write_fragments)
        assert recv_packet(reader) == request()
        writer.result(timeout=5)
    assert reader.calls > 2


def test_coalesced_frames_and_clean_eof(tcp_pair):
    sender, receiver = tcp_pair
    packets = [request(), make_response("req-42", {}), make_event(EventType.USERS_UPDATED, {})]
    sender.sendall(b"".join(map(encode_packet, packets)))
    sender.shutdown(socket.SHUT_WR)
    assert [recv_packet(receiver) for _ in packets] == packets
    assert recv_packet(receiver) is None


def test_clean_eof_without_any_frame(tcp_pair):
    sender, receiver = tcp_pair
    sender.shutdown(socket.SHUT_WR)
    assert recv_packet(receiver) is None


@pytest.mark.parametrize("prefix", [1, 2, 3, 4, 5, 18])
def test_eof_in_header_or_body_is_truncated(tcp_pair, prefix):
    sender, receiver = tcp_pair
    frame = encode_packet(request())
    sender.sendall(frame[:prefix])
    sender.shutdown(socket.SHUT_WR)
    with pytest.raises(IncompleteFrameError) as error:
        recv_packet(receiver)
    assert error.value.expected == (4 if prefix < 4 else len(frame) - 4)
    assert error.value.received == (prefix if prefix < 4 else prefix - 4)


def test_recv_exact_does_not_consume_following_bytes(tcp_pair):
    sender, receiver = tcp_pair
    sender.sendall(b"abcdef")
    assert recv_exact(receiver, 0) == b""
    assert recv_exact(receiver, 2) == b"ab"
    assert recv_exact(receiver, 4) == b"cdef"


@pytest.mark.parametrize("size", [-1, MAX_FRAME_BYTES + 1, True, 1.0])
def test_recv_exact_rejects_invalid_read_size(size):
    with pytest.raises(ValueError):
        recv_exact(None, size)


@pytest.mark.parametrize("size,code", [
    (0, ErrorCode.INVALID_FRAME),
    (MAX_FRAME_BYTES + 1, ErrorCode.FRAME_TOO_LARGE),
    (0xFFFFFFFF, ErrorCode.FRAME_TOO_LARGE),
])
def test_bad_length_rejected_before_any_body_read(tcp_pair, size, code):
    sender, receiver = tcp_pair
    sender.sendall(HEADER.pack(size))

    class HeaderOnly:
        def recv(self, count):
            assert count == HEADER.size, "Must reject header before requesting a body"
            assert not getattr(self, "header_read", False)
            self.header_read = True
            return receiver.recv(count, socket.MSG_WAITALL)

    with pytest.raises(ProtocolError) as error:
        recv_packet(HeaderOnly())
    assert error.value.code == code


def sized_packet(body_size):
    packet = make_event(EventType.GROUPS_UPDATED, {"padding": ""})
    overhead = len(encode_packet(packet)) - HEADER.size
    packet["data"]["padding"] = "x" * (body_size - overhead)
    return packet


def test_exact_one_mib_body_is_accepted_over_tcp(tcp_pair):
    sender, receiver = tcp_pair
    packet = sized_packet(MAX_FRAME_BYTES)
    assert len(encode_packet(packet)) == HEADER.size + MAX_FRAME_BYTES
    with ThreadPoolExecutor(max_workers=1) as pool:
        writer = pool.submit(PacketConnection(sender).send_packet, packet)
        assert recv_packet(receiver) == packet
        writer.result(timeout=5)


def test_oversized_send_writes_nothing_and_connection_stays_usable(tcp_pair):
    sender, receiver = tcp_pair
    connection = PacketConnection(sender)
    with pytest.raises(ProtocolError) as error:
        connection.send_packet(sized_packet(MAX_FRAME_BYTES + 1))
    assert error.value.code == ErrorCode.FRAME_TOO_LARGE
    connection.send_packet(request())
    assert recv_packet(receiver) == request()


@pytest.mark.parametrize("body", [
    b"\xff", b"\xef\xbb\xbf{}", b"{", b"{}{}", b'{"a":1,}',
    b'{"v":1,"v":2}',
    b'{"v":1,"id":"x","type":"LOGIN","data":{"x":1,"x":2}}',
    b'{"v":1,"id":"x","type":"LOGIN","data":{"n":NaN}}',
    b'{"v":1,"id":"x","type":"LOGIN","data":{"n":Infinity}}',
    b'{"v":1,"id":"x","type":"LOGIN","data":{"n":-Infinity}}',
])
def test_invalid_json_and_utf8_over_tcp(tcp_pair, body):
    sender, receiver = tcp_pair
    sender.sendall(raw_frame(body))
    with pytest.raises(ProtocolError) as error:
        recv_packet(receiver)
    assert error.value.code == ErrorCode.INVALID_JSON


@pytest.mark.parametrize("packet", [
    None, [], 42, "text", {},
    {"v": True, "id": "x", "type": "LOGIN", "data": {}},
    {"v": 1.0, "id": "x", "type": "LOGIN", "data": {}},
    {"v": 1, "type": "LOGIN", "data": {}},
    {"v": 1, "id": None, "type": "LOGIN", "data": {}},
    {"v": 1, "id": "", "type": "LOGIN", "data": {}},
    {"v": 1, "id": "ก", "type": "LOGIN", "data": {}},
    {"v": 1, "id": "x" * 65, "type": "LOGIN", "data": {}},
    {"v": 1, "id": "x\n", "type": "LOGIN", "data": {}},
    {"v": 1, "id": 42, "type": "LOGIN", "data": {}},
    {"v": 1, "id": "x", "type": "LOGIN", "data": []},
    {"v": 1, "id": "x", "type": [], "data": {}},
    {"v": 1, "id": "x", "type": "USERS_UPDATED", "data": {}},
    {"v": 1, "type": "USERS_UPDATED", "data": {}, "extra": 1},
    {"v": 1, "id": "x", "type": "LOGIN", "data": {}, "sender_id": 3},
    {"v": 1, "id": "x", "type": "LOGIN", "data": {"text": "\ud800"}},
])
def test_invalid_envelopes_over_tcp(tcp_pair, packet):
    sender, receiver = tcp_pair
    sender.sendall(raw_frame(json.dumps(packet)))
    with pytest.raises(PacketValidationError):
        recv_packet(receiver)


@pytest.mark.parametrize("version,kind,code", [
    (2, "LOGIN", ErrorCode.UNSUPPORTED_VERSION),
    (1, "NOT_A_TYPE", ErrorCode.UNKNOWN_TYPE),
])
def test_version_and_type_codes(tcp_pair, version, kind, code):
    sender, receiver = tcp_pair
    sender.sendall(raw_frame(json.dumps({"v": version, "id": "x", "type": kind, "data": {}})))
    with pytest.raises(PacketValidationError) as error:
        recv_packet(receiver)
    assert error.value.code == code


@pytest.mark.parametrize("data", [
    {}, {"ok": 1, "result": {}}, {"ok": True}, {"ok": True, "result": []},
    {"ok": True, "result": {}, "error": {}},
    {"ok": False}, {"ok": False, "error": "bad"},
    {"ok": False, "error": {"code": "OTHER", "message": "bad"}},
    {"ok": False, "error": {"code": [], "message": "bad"}},
    {"ok": False, "error": {"code": "FORBIDDEN", "message": " "}},
    {"ok": False, "error": {"code": "FORBIDDEN", "message": "x" * 513}},
    {"ok": False, "error": {"code": "FORBIDDEN", "message": "bad", "extra": 1}},
])
def test_invalid_response_shape_over_tcp(tcp_pair, data):
    sender, receiver = tcp_pair
    sender.sendall(raw_frame(json.dumps({"v": 1, "id": "x", "type": "RESPONSE", "data": data})))
    with pytest.raises(PacketValidationError):
        recv_packet(receiver)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), (1, 2), {1: "value"}, b"binary"])
def test_outgoing_non_json_values_rejected_before_write(tcp_pair, value):
    sender, receiver = tcp_pair
    connection = PacketConnection(sender)
    packet = request()
    packet["data"]["bad"] = value
    with pytest.raises(PacketValidationError):
        connection.send_packet(packet)
    connection.send_packet(request())
    assert recv_packet(receiver) == request()


def test_nesting_limit_and_cycles_are_controlled_errors(tcp_pair):
    sender, receiver = tcp_pair
    packet = request()
    nested = packet["data"]
    for _ in range(MAX_JSON_DEPTH):
        nested["nested"] = {}
        nested = nested["nested"]
    sender.sendall(raw_frame(json.dumps(packet)))
    with pytest.raises(PacketValidationError, match="depth"):
        recv_packet(receiver)
    with pytest.raises(PacketValidationError, match="depth"):
        encode_packet(packet)
    cyclic = request()
    cyclic["data"]["cycle"] = cyclic
    with pytest.raises(PacketValidationError, match="circular"):
        encode_packet(cyclic)


def test_extreme_json_nesting_is_a_controlled_error(tcp_pair):
    sender, receiver = tcp_pair
    sender.sendall(raw_frame(b"[" * 2000 + b"0" + b"]" * 2000))
    # Some Python JSON decoders hit their recursion limit before validation.
    with pytest.raises(ProtocolError):
        recv_packet(receiver)


def test_valid_json_number_overflow_is_rejected(tcp_pair):
    sender, receiver = tcp_pair
    sender.sendall(raw_frame(
        '{"v":1,"id":"x","type":"LOGIN","data":{"number":1e999}}'
    ))
    with pytest.raises(PacketValidationError, match="finite"):
        recv_packet(receiver)


def test_builders_validate_ids_types_and_do_not_mutate():
    packet = request()
    original = copy.deepcopy(packet)
    assert validate_packet(packet) is packet
    encode_packet(packet)
    assert packet == original
    ids = {make_request(RequestType.LOGIN, {})["id"] for _ in range(100)}
    assert len(ids) == 100
    assert make_request(RequestType.LOGOUT, {}, request_id="A_1.:z-9")["id"] == "A_1.:z-9"
    with pytest.raises(PacketValidationError):
        make_request(RequestType.LOGIN, {}, request_id="")
    with pytest.raises(ValueError):
        make_request(EventType.MESSAGE_NEW, {})
    with pytest.raises(ValueError):
        make_event(RequestType.LOGIN, {})


def test_every_declared_wire_type_roundtrips(tcp_pair):
    sender, receiver = tcp_pair
    connection = PacketConnection(sender)
    packets = [make_request(kind, {}) for kind in RequestType]
    packets += [make_event(kind, {}) for kind in EventType]
    packets += [make_error("x", code, "เกิดข้อผิดพลาด") for code in ErrorCode]
    for packet in packets:
        connection.send_packet(packet)
        assert recv_packet(receiver) == packet


def test_concurrent_writers_cannot_interleave_real_tcp_frames(tcp_pair):
    sender, receiver = tcp_pair
    workers, per_worker = 6, 20
    start = threading.Barrier(workers)

    class FragmentingWriter:
        """One sendall split across real writes; active overlap is observable."""

        def __init__(self):
            self.active = 0
            self.maximum_active = 0
            self.state_lock = threading.Lock()

        def sendall(self, frame):
            with self.state_lock:
                self.active += 1
                self.maximum_active = max(self.maximum_active, self.active)
            try:
                for offset in range(0, len(frame), 113):
                    sender.sendall(frame[offset:offset + 113])
                    time.sleep(0)  # Let competing writers run inside each sendall.
            finally:
                with self.state_lock:
                    self.active -= 1

    writer_socket = FragmentingWriter()
    connection = PacketConnection(writer_socket)
    text = "ข้อความไทย 🚀" * 70

    def write(worker):
        start.wait(timeout=5)
        for index in range(per_worker):
            connection.send_packet(make_request(
                RequestType.MESSAGE_SEND, {"room_id": 1, "text": text},
                request_id=f"{worker}:{index}",
            ))

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(write, worker) for worker in range(workers)]
        packets = [recv_packet(receiver) for _ in range(workers * per_worker)]
        for future in futures:
            future.result(timeout=5)
    assert {packet["id"] for packet in packets} == {
        f"{worker}:{index}" for worker in range(workers) for index in range(per_worker)
    }
    assert all(packet["data"]["text"] == text for packet in packets)
    assert writer_socket.maximum_active == 1


def test_failed_send_is_not_retried(tcp_pair):
    sender, receiver = tcp_pair

    class FailingWriter:
        calls = 0

        def sendall(self, frame):
            self.calls += 1
            sender.sendall(frame[:5])
            raise OSError("Simulated failure after partial write")

    failing = FailingWriter()
    connection = PacketConnection(failing)
    with pytest.raises(OSError):
        connection.send_packet(request())
    with pytest.raises(ConnectionError, match="previous send failed"):
        connection.send_packet(request())
    assert failing.calls == 1
    sender.shutdown(socket.SHUT_WR)
    with pytest.raises(IncompleteFrameError):
        recv_packet(receiver)


def test_timeout_propagates_instead_of_becoming_clean_eof(tcp_pair):
    sender, receiver = tcp_pair
    sender.sendall(HEADER.pack(10) + b"{")
    receiver.settimeout(0.02)
    with pytest.raises(TimeoutError):
        recv_packet(receiver)


def test_validation_errors_do_not_echo_secrets(tcp_pair):
    sender, receiver = tcp_pair
    secret = "test-password-never-echo"
    sender.sendall(raw_frame('{"password":"' + secret + '",broken}'))
    with pytest.raises(ProtocolError) as error:
        recv_packet(receiver)
    assert secret not in str(error.value)
    assert error.value.__suppress_context__
