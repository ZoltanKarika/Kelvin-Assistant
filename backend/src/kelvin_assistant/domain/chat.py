"""Framework-independent chat domain models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID, uuid4

MAX_MESSAGE_LENGTH = 32_768


class InvalidChatMessageError(ValueError):
    """Raised when chat message content violates domain rules."""


class ChatRole(StrEnum):
    """Roles supported by the conversation domain."""

    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True, slots=True)
class ChatMessage:
    """A validated message stored in a chat session."""

    role: ChatRole
    content: str

    def __post_init__(self) -> None:
        """Normalize and validate message content."""

        normalized_content = self.content.strip()
        if not normalized_content:
            raise InvalidChatMessageError("Chat message cannot be empty")
        if len(normalized_content) > MAX_MESSAGE_LENGTH:
            raise InvalidChatMessageError(
                f"Chat message cannot exceed {MAX_MESSAGE_LENGTH} characters"
            )
        object.__setattr__(self, "content", normalized_content)


@dataclass(frozen=True, slots=True)
class ChatSession:
    """An immutable, versioned conversation session."""

    id: UUID
    messages: tuple[ChatMessage, ...] = ()
    version: int = 0

    @classmethod
    def create(cls) -> ChatSession:
        """Create a new empty session with an opaque identifier."""

        return cls(id=uuid4())

    def append_turn(
        self,
        user_content: str,
        assistant_content: str,
    ) -> ChatSession:
        """Return a new session containing one complete conversation turn."""

        new_messages = (
            ChatMessage(role=ChatRole.USER, content=user_content),
            ChatMessage(role=ChatRole.ASSISTANT, content=assistant_content),
        )
        return ChatSession(
            id=self.id,
            messages=(*self.messages, *new_messages),
            version=self.version + 1,
        )
