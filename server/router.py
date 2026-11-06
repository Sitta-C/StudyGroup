"""Request direction and authentication gate, before feature dispatch."""

import logging

from server.handlers.auth import AuthError
from server.handlers.chat import ChatError
from server.permissions import AccessDenied
from shared.message_types import ErrorCode, RequestType
from shared.protocol import make_error
from shared.validation import ProtocolError


class Router:
    def __init__(self, auth, chat, history=None, files=None):
        self.auth = auth
        self.chat = chat
        self.features = [handler for handler in (history, files) if handler is not None]

    def dispatch(self, connection, db, request):
        if request["type"] not in RequestType:
            # Client-originated events/responses are protocol violations, not commands.
            raise ProtocolError(ErrorCode.INVALID_PACKET, "Expected a client request")
        request_id, kind = request["id"], request["type"]
        try:
            if kind not in (RequestType.REGISTER, RequestType.LOGIN) and connection.user is None:
                raise AuthError(ErrorCode.AUTH_REQUIRED, "Login required")
            if kind in (RequestType.REGISTER, RequestType.LOGIN, RequestType.LOGOUT, RequestType.USERS_LIST):
                self.auth.handle(connection, db, request)
                if kind == RequestType.LOGOUT:
                    # The socket may stay open; unfinished uploads end with the session.
                    for handler in self.features:
                        if hasattr(handler, "connection_closed"):
                            handler.connection_closed(connection)
            elif kind in self.chat.TYPES:
                self.chat.handle(connection, db, request)
            elif handler := next((h for h in self.features if kind in h.TYPES), None):
                handler.handle(connection, db, request)
            else:
                raise AuthError(ErrorCode.UNKNOWN_TYPE, "Request handler is not available yet")
        except (AuthError, ChatError, AccessDenied) as error:
            connection.enqueue(make_error(request_id, error.code, str(error)))
        except Exception:
            logging.getLogger(__name__).error("Request handler failed")
            connection.enqueue(make_error(request_id, ErrorCode.INTERNAL_ERROR, "Request failed"))
