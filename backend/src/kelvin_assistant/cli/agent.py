"""PowerShell-friendly local Kelvin client for safe read-only tools."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from kelvin_assistant.adapters.agent_http import HttpAgentApiClient
from kelvin_assistant.adapters.local_process import AsyncLocalProcessRunner
from kelvin_assistant.adapters.read_tools import (
    FileSearchExecutor,
    GitDiffExecutor,
    GitStatusExecutor,
)
from kelvin_assistant.adapters.write_tools import FilePatchExecutor
from kelvin_assistant.application.local_agent import (
    LocalReadToolClient,
    ToolApprovalRejectedError,
)
from kelvin_assistant.domain.agent import JsonValue
from kelvin_assistant.ports.agent_client import AgentApiClient, AgentClientError
from kelvin_assistant.ports.processes import ProcessRunner
from kelvin_assistant.ports.tools import ToolExecutionError, ToolExecutor

LOGGER = logging.getLogger(__name__)
DEFAULT_API_URL = "http://127.0.0.1:8000"


@dataclass(frozen=True, slots=True)
class ClientCommand:
    """Normalized CLI configuration for one local read tool call."""

    api_url: str
    workspace_id: str
    workspace_root: Path
    tool_name: str
    arguments: Mapping[str, JsonValue]


def build_parser() -> argparse.ArgumentParser:
    """Build the local Kelvin command line parser."""

    parser = argparse.ArgumentParser(
        prog="kelvin",
        description="Run approved Kelvin tools from the local Windows workspace.",
    )
    parser.add_argument(
        "--api-url",
        default=os.getenv("KELVIN_API_URL", DEFAULT_API_URL),
        help="Kelvin Ubuntu API URL.",
    )
    parser.add_argument(
        "--workspace-id",
        default=os.getenv("KELVIN_WORKSPACE_ID"),
        help="Opaque workspace ID configured on the backend.",
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path(os.getenv("KELVIN_WORKSPACE_PATH", ".")),
        help="Local Windows workspace path. Default: current directory.",
    )

    command_parsers = parser.add_subparsers(dest="command", required=True)
    git_parser = command_parsers.add_parser("git", help="Read Git workspace state.")
    git_commands = git_parser.add_subparsers(dest="git_command", required=True)

    status_parser = git_commands.add_parser("status", help="Show concise Git status.")
    status_parser.add_argument(
        "--no-untracked",
        action="store_true",
        help="Hide untracked files.",
    )

    diff_parser = git_commands.add_parser("diff", help="Show Git changes.")
    diff_parser.add_argument("--staged", action="store_true")
    diff_parser.add_argument("--path", help="Optional relative workspace path.")

    file_parser = command_parsers.add_parser(
        "file",
        help="Search or safely update workspace files.",
    )
    file_commands = file_parser.add_subparsers(dest="file_command", required=True)
    search_parser = file_commands.add_parser(
        "search",
        help="Search fixed text in workspace files.",
    )
    search_parser.add_argument("query")
    search_parser.add_argument("--path", help="Optional relative workspace path.")
    search_parser.add_argument(
        "--max-results",
        type=int,
        default=50,
        help="Maximum returned matching lines. Default: 50.",
    )
    patch_parser = file_commands.add_parser(
        "patch",
        help="Preview and approve one exact text replacement.",
    )
    patch_parser.add_argument("path", help="Relative UTF-8 file path.")
    patch_parser.add_argument(
        "--old-text",
        required=True,
        help="Exact text that must occur once.",
    )
    patch_parser.add_argument(
        "--new-text",
        required=True,
        help="Replacement text. May be empty.",
    )
    return parser


def parse_command(
    parser: argparse.ArgumentParser,
    argv: Sequence[str] | None = None,
) -> ClientCommand:
    """Parse and normalize one CLI command."""

    args = parser.parse_args(argv)
    api_url = cast(str, args.api_url).strip()
    workspace_id_value = cast(str | None, args.workspace_id)
    if workspace_id_value is None or not workspace_id_value.strip():
        parser.error("--workspace-id or KELVIN_WORKSPACE_ID is required")
    workspace_id = workspace_id_value.strip()
    workspace_root = cast(Path, args.workspace).resolve(strict=True)
    if not workspace_root.is_dir():
        parser.error("--workspace must point to a directory")

    command = cast(str, args.command)
    if command == "git":
        git_command = cast(str, args.git_command)
        if git_command == "status":
            return ClientCommand(
                api_url=api_url,
                workspace_id=workspace_id,
                workspace_root=workspace_root,
                tool_name="git.status",
                arguments={
                    "include_untracked": not cast(bool, args.no_untracked),
                },
            )
        arguments: dict[str, JsonValue] = {
            "staged": cast(bool, args.staged),
        }
        path = cast(str | None, args.path)
        if path is not None:
            arguments["path"] = path
        return ClientCommand(
            api_url=api_url,
            workspace_id=workspace_id,
            workspace_root=workspace_root,
            tool_name="git.diff",
            arguments=arguments,
        )

    file_command = cast(str, args.file_command)
    if file_command == "search":
        search_arguments: dict[str, JsonValue] = {
            "query": cast(str, args.query),
            "max_results": cast(int, args.max_results),
        }
        search_path = cast(str | None, args.path)
        if search_path is not None:
            search_arguments["path"] = search_path
        return ClientCommand(
            api_url=api_url,
            workspace_id=workspace_id,
            workspace_root=workspace_root,
            tool_name="file.search",
            arguments=search_arguments,
        )

    return ClientCommand(
        api_url=api_url,
        workspace_id=workspace_id,
        workspace_root=workspace_root,
        tool_name="file.patch",
        arguments={
            "path": cast(str, args.path),
            "old_text": cast(str, args.old_text),
            "new_text": cast(str, args.new_text),
        },
    )


async def execute_command(
    command: ClientCommand,
    *,
    api_client: AgentApiClient | None = None,
    process_runner: ProcessRunner | None = None,
    approval_prompt: Callable[[str], bool] | None = None,
) -> int:
    """Execute one parsed command and print its bounded result."""

    active_api_client = api_client or HttpAgentApiClient(command.api_url)
    active_process_runner = process_runner or AsyncLocalProcessRunner()
    executors: dict[str, ToolExecutor] = {
        "git.status": GitStatusExecutor(active_process_runner),
        "git.diff": GitDiffExecutor(active_process_runner),
        "file.search": FileSearchExecutor(active_process_runner),
        "file.patch": FilePatchExecutor(),
    }
    client = LocalReadToolClient(
        api_client=active_api_client,
        executors=executors,
        workspace_id=command.workspace_id,
        workspace_root=command.workspace_root,
        approval_handler=approval_prompt or _prompt_for_approval,
    )
    result = await client.run_tool(command.tool_name, command.arguments)
    if result.execution.output:
        print(result.execution.output)
    if result.execution.truncated:
        print("[output truncated]")
    if not result.execution.succeeded:
        LOGGER.error("%s", result.execution.error)
        return 1
    return 0


def _prompt_for_approval(preview: str) -> bool:
    """Show the complete diff and accept only an explicit yes."""

    print("\nProposed change:\n")
    print(preview, end="" if preview.endswith("\n") else "\n")
    answer = input("\nApply this change? [y/N] ")
    return answer.strip().lower() in {"y", "yes"}


def main(argv: Sequence[str] | None = None) -> int:
    """Run the local Kelvin client and return a process exit code."""

    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    parser = build_parser()
    try:
        command = parse_command(parser, argv)
        return asyncio.run(execute_command(command))
    except ToolApprovalRejectedError:
        LOGGER.info("Tool change was not applied")
        return 0
    except (AgentClientError, ToolExecutionError, OSError, ValueError) as exc:
        LOGGER.error("Kelvin command failed: %s", exc)
        return 1
