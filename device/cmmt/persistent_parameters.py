"""Versioned, explicitly selected CMMT persistence contract (RF-017)."""
from device.cmmt.required_non_pdo_od import NON_PDO_CONFIGURATION_OD_ROLES

PARAMETER_SCHEMA_VERSION = 1
PERSISTENT_ADDRESSES = (
    (0x216E, 1),
    (0x2194, 1), (0x2194, 2), (0x2194, 3), (0x2194, 4),
    (0x607D, 1), (0x607D, 2),
    (0x6067, 0), (0x6068, 0),
    (0x607F, 0), (0x2183, 12),
    (0x6083, 0), (0x6084, 0),
    (0x6098, 0), (0x6099, 1), (0x6099, 2), (0x609A, 0),
    (0x60C5, 0), (0x60C6, 0), (0x60A4, 1),
)
_roles = {(role.index, role.subindex): role for role in NON_PDO_CONFIGURATION_OD_ROLES}
PERSISTENT_PARAMETER_ROLES = tuple(_roles[address] for address in PERSISTENT_ADDRESSES)
