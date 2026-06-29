"""Application service for chat turns."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from uuid import UUID

from kelvin_assistant.domain.chat import ChatMessage, ChatRole, ChatSession
from kelvin_assistant.ports.llm import LLMProvider
from kelvin_assistant.ports.sessions import SessionStore


@dataclass(frozen=True, slots=True)
class ChatResult:
    """Result returned after a complete chat turn is persisted."""

    session_id: UUID
    message: str


@dataclass(frozen=True, slots=True)
class ChatStreamResult:
    """Result returned before a streaming chat turn starts emitting text."""

    session_id: UUID
    chunks: AsyncIterator[str]


class ChatService:
    """Coordinate chat context, model invocation, and session persistence."""

    def __init__(
        self,
        llm_provider: LLMProvider,
        session_store: SessionStore,
        history_turn_limit: int = 10,
        system_prompt: str | None = None,
    ) -> None:
        if history_turn_limit <= 0:
            msg = "history_turn_limit must be positive"
            raise ValueError(msg)
        self._llm_provider = llm_provider
        self._session_store = session_store
        self._history_message_limit = history_turn_limit * 2
        self._system_message = (
            ChatMessage(role=ChatRole.SYSTEM, content=system_prompt)
            if system_prompt is not None
            else None
        )

    async def send_message(
        self,
        message: str,
        session_id: UUID | None = None,
    ) -> ChatResult:
        """Generate and atomically persist one complete conversation turn."""

        user_message = ChatMessage(role=ChatRole.USER, content=message)
        if session_id is None:
            is_new_session = True
            session = ChatSession.create()
        else:
            is_new_session = False
            session = await self._session_store.get(session_id)

        conversation_context = (
            *session.messages[-self._history_message_limit :],
            user_message,
        )
        context = (
            (self._system_message, *conversation_context)
            if self._system_message is not None
            else conversation_context
        )
        assistant_content = await self._llm_provider.chat(context)
        updated_session = session.append_turn(
            user_content=user_message.content,
            assistant_content=assistant_content,
        )

        if is_new_session:
            await self._session_store.add(updated_session)
        else:
            await self._session_store.update(
                updated_session,
                expected_version=session.version,
            )

        return ChatResult(
            session_id=updated_session.id,
            message=updated_session.messages[-1].content,
        )

    async def stream_message(
        self,
        message: str,
        session_id: UUID | None = None,
    ) -> ChatStreamResult:
        """Stream and persist one complete conversation turn."""

        user_message = ChatMessage(role=ChatRole.USER, content=message)
        if session_id is None:
            is_new_session = True
            session = ChatSession.create()
        else:
            is_new_session = False
            session = await self._session_store.get(session_id)

        conversation_context = (
            *session.messages[-self._history_message_limit :],
            user_message,
        )
        context = (
            (self._system_message, *conversation_context)
            if self._system_message is not None
            else conversation_context
        )

        async def chunks() -> AsyncIterator[str]:
            assistant_chunks: list[str] = []
            async for chunk in self._llm_provider.stream_chat(context):
                assistant_chunks.append(chunk)
                yield chunk

            assistant_content = "".join(assistant_chunks)
            updated_session = session.append_turn(
                user_content=user_message.content,
                assistant_content=assistant_content,
            )

            if is_new_session:
                await self._session_store.add(updated_session)
            else:
                await self._session_store.update(
                    updated_session,
                    expected_version=session.version,
                )

        return ChatStreamResult(session_id=session.id, chunks=chunks())
