from dataclasses import dataclass

from kelvin_assistant.domain.input_guard import InputGuard, InputValidationResult


@dataclass(frozen=True)
class GuardedContent:
    """Wrapped and sanitized external content."""

    text: str
    is_safe: bool
    warnings: list[str]


class ContextGuard:
    """
    Wraps external data in strict delimiters to separate it from instructions.
    """

    BEGIN_DELIMITER = "--- BEGIN EXTERNAL DATA ---"
    END_DELIMITER = "--- END EXTERNAL DATA ---"

    def __init__(self, input_guard: InputGuard) -> None:
        self._input_guard = input_guard

    def wrap(self, text: str, source: str = "unknown") -> GuardedContent:
        """
        Wraps external text in delimiters after checking for injection attacks.

        Args:
            text: The external content to wrap.
            source: The origin of the content (e.g., URL, file path).

        Returns:
            A GuardedContent object with the wrapped text and safety information.
        """
        # Step 1: Check for embedded injection attacks using InputGuard
        validation_result: InputValidationResult = self._input_guard.validate_input(
            text
        )
        if not validation_result.is_safe:
            return GuardedContent(
                text="",
                is_safe=False,
                warnings=[
                    (
                        f"Input from source '{source}' blocked due to potential "
                        "injection attacks."
                    ),
                    *validation_result.warnings,
                ],
            )

        # Step 2: Escape any potential delimiter impersonators within the text
        escaped_text = self._escape_delimiters(text)

        # Step 3: Wrap the sanitized content in strict delimiters
        wrapped_text = (
            f"\n{self.BEGIN_DELIMITER}\n{escaped_text}\n{self.END_DELIMITER}\n"
        )

        return GuardedContent(
            text=wrapped_text,
            is_safe=True,
            warnings=validation_result.warnings,
        )

    def _escape_delimiters(self, text: str) -> str:
        """
        Escapes any occurrences of the delimiters within the text to prevent
        the LLM from misinterpreting them.
        """
        escaped_text = text.replace(self.BEGIN_DELIMITER, "--- BEGIN ESCAPED DATA ---")
        escaped_text = escaped_text.replace(
            self.END_DELIMITER, "--- END ESCAPED DATA ---"
        )
        return escaped_text
