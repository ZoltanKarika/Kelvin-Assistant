"""Unit tests for chat domain models."""

import pytest

from kelvin_assistant.domain.chat import (
    MAX_MESSAGE_LENGTH,
    ChatMessage,
    ChatRole,
    ChatSession,
    InvalidChatMessageError,
)


def test_chat_message_normalizes_surrounding_whitespace() -> None:
    """Message content is normalized once at the domain boundary."""

    message = ChatMessage(role=ChatRole.USER, content="  Szia!  ")

    assert message.content == "Szia!"


@pytest.mark.parametrize("content", ["", " ", "\n\t"])
def test_chat_message_rejects_blank_content(content: str) -> None:
    """Blank messages cannot enter conversation state."""

    with pytest.raises(
        InvalidChatMessageError,
        match="Chat message cannot be empty",
    ):
        ChatMessage(role=ChatRole.USER, content=content)


def test_chat_message_rejects_content_above_limit() -> None:
    """Oversized messages are rejected before model invocation."""

    with pytest.raises(
        InvalidChatMessageError,
        match=f"Chat message cannot exceed {MAX_MESSAGE_LENGTH} characters",
    ):
        ChatMessage(
            role=ChatRole.USER,
            content="a" * (MAX_MESSAGE_LENGTH + 1),
        )


def test_session_create_returns_empty_versioned_session() -> None:
    """A new session starts without messages at version zero."""

    session = ChatSession.create()

    assert session.messages == ()
    assert session.version == 0


def test_append_turn_returns_new_session_with_atomic_turn() -> None:
    """A complete user-assistant turn is appended without mutation."""

    original = ChatSession.create()

    updated = original.append_turn(
        user_content="Szia!",
        assistant_content="Szia! Miben segíthetek?",
    )

    assert original.messages == ()
    assert original.version == 0
    assert updated.id == original.id
    assert updated.version == 1
    assert updated.messages == (
        ChatMessage(role=ChatRole.USER, content="Szia!"),
        ChatMessage(
            role=ChatRole.ASSISTANT,
            content="Szia! Miben segíthetek?",
        ),
    )
