import re
from dataclasses import dataclass


@dataclass(frozen=True)
class InputValidationResult:
    is_safe: bool
    warnings: list[str]


class InputGuard:
    # Pattern groups for dangerous intents
    _DANGEROUS_INTENTS = [
        (
            r"\b(rm\s+-rf\b|sudo\b|format\s+c:|cmd\.exe|powershell\b|bash\b|mkfs\b|rd\s+/s\b)",
            "Dangerous system commands or shell execution detected",
        ),
        (
            r"(\betc/hosts\b|C:\\Windows\\System32\b|\bhosts\s+file\b)",
            "System file modification or inspection detected",
        ),
        (
            r"\b(bypass\s+security\b|disable\s+firewall\b|disable\s+security\b|override\s+policy\b|disable\s+approval\b)",
            "Security bypass attempt detected",
        ),
        (
            r"\.\./\.\.|/etc/passwd",
            "Workspace escape or directory traversal attempt detected",
        ),
    ]

    # Pattern groups for credential harvesting
    _CREDENTIAL_REQUESTS = [
        (
            r"\.env\b",
            "Attempt to read environment configuration file (.env) detected",
        ),
        (
            r"\b(id_rsa\b|id_dsa\b|id_ed25519\b|private\s+key\b)",
            "Attempt to read private key credentials detected",
        ),
        (
            r"\b(connection\s+string\b|postgres(ql)?://|db_password\b|api_key\b|api_token\b)",
            "Attempt to extract database or API credentials detected",
        ),
    ]

    # Pattern groups for prompt injection/jailbreaks
    _ADVANCED_INJECTION = [
        (
            r"\b(ignore\s+previous\s+instructions|ignore\s+the\s+above|you\s+are\s+now\b|acting\s+as\b|system\s+prompt\b|developer\s+mode\b|ignore\s+directives|ignore\s+safety|bypass\s+alignment)\b",
            "Jailbreak or system prompt override attempt detected",
        ),
        (
            r"(</?system>|</?user>|</?assistant>|\[SYSTEM\]|\[USER\]|\[ASSISTANT\])",
            "Prompt boundary escape or tag spoofing attempt detected",
        ),
    ]

    def detect_dangerous_intent(self, text: str) -> list[str]:
        """Scans for dangerous system actions or security overrides."""
        warnings = []
        for pattern, warning in self._DANGEROUS_INTENTS:
            if re.search(pattern, text, re.IGNORECASE):
                warnings.append(warning)
        return warnings

    def detect_credential_requests(self, text: str) -> list[str]:
        """Scans for credential retrieval or password/key harvesting."""
        warnings = []
        for pattern, warning in self._CREDENTIAL_REQUESTS:
            if re.search(pattern, text, re.IGNORECASE):
                warnings.append(warning)
        return warnings

    def detect_advanced_injection(self, text: str) -> list[str]:
        """Scans for jailbreaks, instructions overrides, and XML tag spoofing."""
        warnings = []
        for pattern, warning in self._ADVANCED_INJECTION:
            if re.search(pattern, text, re.IGNORECASE):
                warnings.append(warning)
        return warnings

    def validate_input(self, text: str) -> InputValidationResult:
        """Combines all scan layers and returns a safety decision."""
        warnings = []
        warnings.extend(self.detect_dangerous_intent(text))
        warnings.extend(self.detect_credential_requests(text))
        warnings.extend(self.detect_advanced_injection(text))

        is_safe = len(warnings) == 0
        return InputValidationResult(is_safe=is_safe, warnings=warnings)
