"""In-memory registry for immutable agent tool definitions."""

from collections.abc import Iterable, Mapping
from types import MappingProxyType

from kelvin_assistant.domain.agent import ToolDefinition
from kelvin_assistant.ports.tools import DuplicateToolError, UnknownToolError


class StaticToolRegistry:
    """A validated tool catalog assembled during application startup."""

    def __init__(self, definitions: Iterable[ToolDefinition] = ()) -> None:
        """Build a registry and reject duplicate tool names."""

        registered: dict[str, ToolDefinition] = {}
        for definition in definitions:
            if definition.name in registered:
                raise DuplicateToolError(
                    f"Tool '{definition.name}' is already registered"
                )
            registered[definition.name] = definition
        self._definitions: Mapping[str, ToolDefinition] = MappingProxyType(registered)

    def get(self, name: str) -> ToolDefinition:
        """Return one definition by its exact registered name."""

        try:
            return self._definitions[name]
        except KeyError as error:
            raise UnknownToolError(f"Tool '{name}' is not registered") from error

    def list_all(self) -> tuple[ToolDefinition, ...]:
        """Return definitions in deterministic name order."""

        return tuple(self._definitions[name] for name in sorted(self._definitions))
