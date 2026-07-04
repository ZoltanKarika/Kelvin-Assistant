"""
Input validation to detect and prevent prompt injection, dangerous intent,
and credential requests.
"""

import re
from dataclasses import dataclass
from enum import StrEnum


class InputValidationStatus(StrEnum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"


@dataclass(frozen=True)
class InputValidationResult:
    status: InputValidationStatus
    warnings: list[str]


DANGEROUS_INTENT_PATTERNS = {
    "arbitrary_command": re.compile(
        r"run command|execute command|run shell|execute shell", re.IGNORECASE
    ),
    "edit_host_files": re.compile(r"edit( my| the)? hosts? file", re.IGNORECASE),
    "delete_files_outside_workspace": re.compile(
        r"delete.*?file|remove.*?file", re.IGNORECASE
    ),
    "bypass_security": re.compile(
        r"bypass security|disable security|ignore rules", re.IGNORECASE
    ),
}


def detect_dangerous_intent(text: str) -> list[str]:
    """
    Scans for phrases asking to run arbitrary commands, edit host files directly,
    delete files outside of the workspace, or bypass security rules.
    """
    warnings = []
    for intent, pattern in DANGEROUS_INTENT_PATTERNS.items():
        if pattern.search(text):
            warnings.append(f"Detected dangerous intent: {intent}")
    return warnings


CREDENTIAL_REQUEST_PATTERNS = {
    "read_env_file": re.compile(r"read.*\.env", re.IGNORECASE),
    "read_ssh_key": re.compile(r"read.*(id_rsa|ssh_config)", re.IGNORECASE),
    "extract_password": re.compile(
        r"extract\s+(the\s+)?password|get\s+(the\s+)?password", re.IGNORECASE
    ),
    "print_connection_string": re.compile(
        r"print.*connection string|get.*connection string", re.IGNORECASE
    ),
}


def detect_credential_requests(text: str) -> list[str]:
    """
    Scans for requests asking to read .env files, read ssh private keys,
    extract passwords, or print database connection strings.
    """
    warnings = []
    for intent, pattern in CREDENTIAL_REQUEST_PATTERNS.items():
        if pattern.search(text):
            warnings.append(f"Detected credential request: {intent}")
    return warnings


ADVANCED_INJECTION_PATTERNS = {
    "ignore_previous_instructions": re.compile(
        r"ignore previous instructions|ignore all prior instructions", re.IGNORECASE
    ),
    "system_prompt_override": re.compile(
        r"you are now a root shell|you are now an unfiltered bot", re.IGNORECASE
    ),
    "xml_escape_trick": re.compile(r"<</?tool_code>>", re.IGNORECASE),
}


def detect_advanced_injection(text: str) -> list[str]:
    """
    Scans for jailbreaks, system prompt overrides ("ignore previous instructions",
    "you are now a root shell"), and XML/HTML-style tag escape tricks.
    """
    warnings = []
    for intent, pattern in ADVANCED_INJECTION_PATTERNS.items():
        if pattern.search(text):
            warnings.append(f"Detected advanced injection: {intent}")
    return warnings


def validate_input(text: str) -> InputValidationResult:
    """
    Combines checks and returns an outcome (ALLOW, BLOCK) with detail warnings.
    """
    all_warnings = (
        detect_dangerous_intent(text)
        + detect_credential_requests(text)
        + detect_advanced_injection(text)
    )

    status = (
        InputValidationStatus.BLOCK if all_warnings else InputValidationStatus.ALLOW
    )

    return InputValidationResult(status=status, warnings=all_warnings)
