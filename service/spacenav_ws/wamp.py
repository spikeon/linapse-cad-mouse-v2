"""Basic WAMP V1 protocol."""

import asyncio
import logging
import random
import string
from enum import IntEnum
from types import CoroutineType
from typing import Any, ClassVar, Dict, NamedTuple, Optional, Type, Callable

from fastapi import WebSocket


def _rand_id(len) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=len))


class WAMP_MSG_TYPE(IntEnum):
    WELCOME = 0
    PREFIX = 1
    CALL = 2
    CALLRESULT = 3
    CALLERROR = 4
    SUBSCRIBE = 5
    UNSUBSCRIBE = 6
    PUBLISH = 7
    EVENT = 8


class WampMessage(tuple[Any, ...]):
    # This WampMessage class maintains a classvariable with all the registered message types!
    REGISTRY: Dict[WAMP_MSG_TYPE, Type["WampMessage"]] = {}
    MSG_TYPE: ClassVar[WAMP_MSG_TYPE]

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        WampMessage.REGISTRY[cls.MSG_TYPE] = cls

    def serialize(self) -> list[Any]:
        return list(self)

    def serialize_with_msg_id(self) -> list[Any]:
        return [self.MSG_TYPE, *self.serialize()]


class Welcome(NamedTuple("WelcomeBase", [("session_id", str), ("version", int), ("server_ident", str)]), WampMessage):
    MSG_TYPE: ClassVar[WAMP_MSG_TYPE] = WAMP_MSG_TYPE.WELCOME


class Prefix(NamedTuple("PrefixBase", [("prefix", str), ("uri", str)]), WampMessage):
    MSG_TYPE: ClassVar[WAMP_MSG_TYPE] = WAMP_MSG_TYPE.PREFIX


class Call(NamedTuple("CallBase", [("call_id", str), ("proc_uri", str), ("args", list[Any])]), WampMessage):
    MSG_TYPE: ClassVar[WAMP_MSG_TYPE] = WAMP_MSG_TYPE.CALL

    def __new__(cls, call_id: str, proc_uri: str, *args: Any):
        return super().__new__(cls, call_id, proc_uri, list(args))

    def serialize(self) -> list[Any]:
        return [self.call_id, self.proc_uri, *self.args]

    @classmethod
    def create(cls, proc_uri: str, *args: Any):
        return Call(_rand_id(18), proc_uri, *args)


class CallResult(NamedTuple("CallResultBase", [("call_id", str), ("result", Any)]), WampMessage):
    MSG_TYPE: ClassVar[WAMP_MSG_TYPE] = WAMP_MSG_TYPE.CALLRESULT


class CallError(NamedTuple("CallErrorBase", [("call_id", str), ("error_uri", str), ("desc", str), ("details", Optional[Any])]), WampMessage):
    MSG_TYPE: ClassVar[WAMP_MSG_TYPE] = WAMP_MSG_TYPE.CALLERROR

    def __new__(cls, call_id: str, error_uri: str, desc: str, details: Optional[Any] = None):
        return super().__new__(cls, call_id, error_uri, desc, details)


class Subscribe(NamedTuple("SubscribeBase", [("topic", str)]), WampMessage):
    MSG_TYPE: ClassVar[WAMP_MSG_TYPE] = WAMP_MSG_TYPE.SUBSCRIBE


class Unsubscribe(NamedTuple("UnsubscribeBase", [("topic", str)]), WampMessage):
    MSG_TYPE: ClassVar[WAMP_MSG_TYPE] = WAMP_MSG_TYPE.UNSUBSCRIBE


class Publish(NamedTuple("PublishBase", [("topic", str), ("payload", Any)]), WampMessage):
    MSG_TYPE: ClassVar[WAMP_MSG_TYPE] = WAMP_MSG_TYPE.PUBLISH


class Event(NamedTuple("EventBase", [("topic", str), ("payload", Any)]), WampMessage):
    MSG_TYPE: ClassVar[WAMP_MSG_TYPE] = WAMP_MSG_TYPE.EVENT


class WampProtocol:
    """
    https://wamp-proto.org/wamp_bp_latest_ietf.html#name-session-establishment Offcourse nothing is compliant and the Onshape client doesn't even send a HELLO lol.
    """

    def __init__(self, websocket: WebSocket):
        self._socket = websocket
        self._server_id = "snbridge v0.0.1"
        self._session_id = _rand_id(16)

        self.prefixes = {}
        self.call_handlers: dict[str, Callable[..., CoroutineType[Any, Any, None]]] = {}
        self.subscribe_handlers: dict[str, Callable[[Subscribe], CoroutineType[Any, Any, None]]] = {}

    async def begin(self):
        await self._socket.accept(subprotocol="wamp")
        await self.send_message(Welcome(self._session_id, 1, self._server_id))

    async def send_message(self, msg: WampMessage):
        logging.debug(f"sending WAMP message: {msg=}")
        await self._socket.send_json(msg.serialize_with_msg_id())

    async def next_message(self) -> WampMessage:
        data = await self._socket.receive_json()
        msg_type = WAMP_MSG_TYPE(data[0])
        msg = WampMessage.REGISTRY[msg_type](*data[1:])
        logging.debug(f"received WAMP message: {msg=}")
        return msg

    async def run_message_handler(self, msg: WampMessage):
        # Introspect WampSession class for handlers called handle_{msg_type}
        handler = getattr(self, f"handle_{msg.MSG_TYPE.name.lower()}", self._handle_unimplemented_msg)
        return await handler(msg)

    async def _handle_unimplemented_msg(self, msg: WampMessage):
        logging.warning("Unhandled WAMP message type: %s", msg.MSG_TYPE)

    async def handle_prefix(self, msg: Prefix):
        self.prefixes[msg.prefix] = msg.uri

    async def handle_call(self, msg: Call):
        rpc_name = self.resolve(msg.proc_uri)
        rpc = self.call_handlers.get(rpc_name)

        if rpc is None:
            logging.warning("Unhandled WAMP RPC: %s", msg.proc_uri)
            await self.send_message(CallError(msg.call_id, "wamp.error.not_found", f"RPC {msg.proc_uri!r} not registered", details=None))
        else:
            await self.send_message(CallResult(msg.call_id, await rpc(*msg.args)))

    async def handle_subscribe(self, msg: Subscribe):
        topic = self.resolve(msg.topic)
        handler = self.subscribe_handlers.get(topic)
        if handler is None:
            logging.warning("Unknown subscribable: %s", topic)
        else:
            logging.debug(f"handle subscribe to '{topic}' by calling: {handler}")
            await handler(msg)

    async def handle_callresult(self, msg: CallResult):
        logging.warning("No callresult handler for msg: %s", msg)

    async def handle_callerror(self, msg: CallError):
        logging.warning("No callerror handler for msg: %s", msg)

    def resolve(self, uri: str) -> str:
        """Resolve any registered prefixes in the uri"""
        prefix, res = uri.split(":", 1)
        return self.prefixes.get(prefix, "") + res


class WampSession:
    """I'm honestly not even sure I should be keeping track of those rpcs? Maybe this whole stateHandler on top the WampProtocol is useless?"""

    def __init__(self, websocket: WebSocket):
        self.wamp = WampProtocol(websocket)

        self.in_flight_rpcs: dict[str, dict] = {}

        self.wamp.handle_callresult = self.handle_callresult
        self.wamp.handle_callerror = self.handle_callerror

    async def start_wamp_message_stream(self):
        while True:
            msg = await self.wamp.next_message()
            # They're all like.. interleaved.. have to create one task per message with the current approach.. Not very nice because it means errors don't bubble up
            asyncio.create_task(self.wamp.run_message_handler(msg))

    async def client_rpc(self, controller_uri: str, method: str, *args):
        """This function lives for the duration of the rpc. It registers the inflight request and waits for either handle_callresult or handle_callerror to finalize the rpc.."""
        call = Call.create(method, "", *args)
        # Launch RPC in background as task. I guess? This is pretty unclear to me? Why are the calls wrapped in Events? Because of the Subscription?
        await self.wamp.send_message(Event(controller_uri, call.serialize_with_msg_id()))

        rpc = {"gate": asyncio.Event(), "result": None, "error": None}

        self.in_flight_rpcs[call.call_id] = rpc
        await rpc["gate"].wait()
        del self.in_flight_rpcs[call.call_id]

        if rpc["error"] is not None:
            logging.error('Encountered error "%s" during %s', rpc["error"], call)
            raise ValueError(rpc["error"])
        return rpc["result"]

    async def handle_callresult(self, msg: CallResult):
        rpc = self.in_flight_rpcs[msg.call_id]
        rpc["result"] = msg.result
        rpc["gate"].set()

    async def handle_callerror(self, msg: CallError):
        rpc = self.in_flight_rpcs[msg.call_id]
        rpc["error"] = (msg.error_uri, msg.desc)
        rpc["gate"].set()
