from dataclasses import dataclass


@dataclass(frozen=True)
class InputValidationResult:
    is_safe: bool
    warnings: list[str]


class InputGuard:
    def validate_input(self, text: str) -> InputValidationResult:
        return InputValidationResult(is_safe=True, warnings=[])
