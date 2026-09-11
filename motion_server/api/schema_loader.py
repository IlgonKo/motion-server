"""Load the local API contracts once; never retrieve schemas from the network."""

import json
import math
from functools import lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from referencing import Registry, Resource


SCHEMA_DIRECTORY = Path(__file__).with_name("schema")
SCHEMA_FILES = ("common.json", "system.json", "axis.json", "io.json", "bus.json", "simulation.json")


def _unique_members(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate schema member: {key}")
        result[key] = value
    return result


def _references(value):
    if isinstance(value, dict):
        if "$ref" in value:
            yield value["$ref"]
        for item in value.values():
            yield from _references(item)
    elif isinstance(value, list):
        for item in value:
            yield from _references(item)


def _nonfinite_values(value, path=()):
    if isinstance(value, float) and not math.isfinite(value):
        yield ValidationError("JSON numbers must be finite", path=path)
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _nonfinite_values(item, (*path, key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _nonfinite_values(item, (*path, index))


class ApiContracts:
    def __init__(self, directory=SCHEMA_DIRECTORY):
        self.documents = {}
        for filename in SCHEMA_FILES:
            path = Path(directory) / filename
            document = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_members)
            Draft202012Validator.check_schema(document)
            if document["$id"] in self.documents:
                raise ValueError(f"Duplicate schema ID: {document['$id']}")
            self.documents[document["$id"]] = document
        self.registry = Registry().with_resources(
            (uri, Resource.from_contents(document))
            for uri, document in self.documents.items()
        )
        self.commands = {}
        self.validators = {}
        for uri, document in self.documents.items():
            resolver = self.registry.resolver(uri)
            for reference in _references(document):
                resolver.lookup(reference)
            for key, definition in document.get("$defs", {}).items():
                metadata = definition.get("x-motion-server")
                if metadata is None:
                    continue
                name = metadata["name"]
                if name in self.commands:
                    raise ValueError(f"Duplicate API command: {name}")
                if metadata["kind"] not in {"authority", "command", "status"}:
                    raise ValueError(f"Invalid command kind: {name}")
                for flag in ("authority_required", "advanced_only", "degraded_allowed", "transport_required"):
                    if type(metadata.get(flag)) is not bool:
                        raise ValueError(f"Invalid {flag} for command: {name}")
                if definition["properties"]["cmd"] != {"const": name}:
                    raise ValueError(f"Inconsistent command name: {name}")
                self.commands[name] = metadata
                self.validators[name] = Draft202012Validator(
                    {"$ref": f"{uri}#/$defs/{key}"}, registry=self.registry,
                )

    def request_errors(self, name, request):
        """Structural validation only; runtime authority/device checks remain in validator."""
        yield from _nonfinite_values(request)
        yield from self.validators[name].iter_errors(request)

    def response_validator(self, name):
        """For contract tests/tooling, not the live response path."""
        metadata = self.commands[name]
        return Draft202012Validator(metadata["response"], registry=self.registry)

    def feedback_validator(self):
        """For contract tests/tooling, not the live feedback path."""
        return Draft202012Validator(
            {"$ref": "https://motion-server.local/schema/system.json#/$defs/feedback"},
            registry=self.registry,
        )


@lru_cache(maxsize=1)
def api_contracts():
    return ApiContracts()
