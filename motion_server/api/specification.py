from dataclasses import dataclass
from motion_server.api.schema_loader import api_contracts


@dataclass(frozen=True)
class CommandSpec:
    name: str
    kind: str
    authority_required: bool = False
    advanced_only: bool = False
    degraded_allowed: bool = False
    transport_required: bool = False

    @property
    def is_command(self):
        return self.kind == "command"

    @property
    def is_status(self):
        return self.kind == "status"

    @property
    def is_authority(self):
        return self.kind == "authority"


def command(
    name,
    authority_required=True,
    advanced_only=False,
    degraded_allowed=False,
    transport_required=False,
):
    return CommandSpec(
        name,
        "command",
        authority_required=authority_required,
        advanced_only=advanced_only,
        degraded_allowed=degraded_allowed,
        transport_required=transport_required,
    )


def status(
    name,
    advanced_only=False,
    degraded_allowed=False,
    transport_required=False,
):
    return CommandSpec(
        name,
        "status",
        advanced_only=advanced_only,
        degraded_allowed=degraded_allowed,
        transport_required=transport_required,
    )


def authority(name):
    return CommandSpec(name, "authority", degraded_allowed=True)


COMMAND_SPECS = {
    name: CommandSpec(**{
        key: value for key, value in metadata.items()
        if key != "response"
    })
    for name, metadata in api_contracts().commands.items()
}


def command_spec(name):
    return COMMAND_SPECS.get(str(name or "").strip())


def command_names():
    return set(COMMAND_SPECS)


def command_message_types():
    return {
        name
        for name, spec in COMMAND_SPECS.items()
        if spec.is_command and spec.authority_required
    }


def authority_message_types():
    return {
        name
        for name, spec in COMMAND_SPECS.items()
        if spec.is_authority
    }


def status_message_types():
    return {
        name
        for name, spec in COMMAND_SPECS.items()
        if spec.is_status
    }


def advanced_message_types():
    return {
        name
        for name, spec in COMMAND_SPECS.items()
        if spec.advanced_only and spec.is_command
    }


def advanced_status_message_types():
    return {
        name
        for name, spec in COMMAND_SPECS.items()
        if spec.advanced_only and spec.is_status
    }


def degraded_allowed_message_types():
    return {
        name
        for name, spec in COMMAND_SPECS.items()
        if spec.degraded_allowed
    }
