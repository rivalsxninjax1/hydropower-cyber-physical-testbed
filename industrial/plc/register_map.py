"""
Modbus holding-register map for the simulated intake-gate PLC.

Modbus documentation convention numbers holding registers 40001-49999;
the wire protocol and pymodbus itself use zero-based addresses. This
module is the single source of truth for both numbering schemes, so
the PLC server, test clients, and later the attacker's tools (Phase 8
onward) all agree on exactly the same map.

All register values are unsigned 16-bit integers (0-65535). Values
with a fractional part are stored as fixed-point integers using the
`scale` factor below (e.g. 45.6% is stored as 456, scale=10) and must
be divided back down by whoever reads them.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RegisterDef:
    modbus_address: int       # conventional 4xxxx address, for documentation
    zero_based_address: int   # actual address used in pymodbus calls
    name: str
    scale: float               # divide raw register value by this for the real value
    writable: bool
    description: str


REGISTERS = [
    RegisterDef(40001, 0, "RESERVOIR_LEVEL_PCT", 10.0, False,
                "Reservoir level, percent of operating band, x10 fixed-point."),
    RegisterDef(40002, 1, "GATE_POSITION_PCT", 10.0, False,
                "Actual (measured) gate position, percent open, x10 fixed-point."),
    RegisterDef(40003, 2, "FLOW_RATE_M3S", 10.0, False,
                "Flow through the gate, cubic metres/second, x10 fixed-point."),
    RegisterDef(40004, 3, "TURBINE_RPM", 1.0, False,
                "Turbine rotational speed, RPM, integer."),
    RegisterDef(40005, 4, "GENERATOR_POWER_MW", 10.0, False,
                "Generator power output, megawatts, x10 fixed-point."),
    RegisterDef(40006, 5, "ALARM_STATE", 1.0, False,
                "0 = NORMAL, 1 = WARNING, 2 = CRITICAL."),
    RegisterDef(40007, 6, "GATE_TARGET_COMMAND_PCT", 10.0, True,
                "Commanded gate target, percent open, x10 fixed-point. "
                "WRITABLE — this is the plant's only control register."),
]

ALARM_STATE_CODES = {"NORMAL": 0, "WARNING": 1, "CRITICAL": 2}
ALARM_STATE_NAMES = {v: k for k, v in ALARM_STATE_CODES.items()}

REGISTER_COUNT = len(REGISTERS)


def by_name(name: str) -> RegisterDef:
    for reg in REGISTERS:
        if reg.name == name:
            return reg
    raise KeyError(f"No register named {name!r}")


def encode(name: str, real_value: float) -> int:
    """Convert a real-world value into the raw uint16 stored on the register."""
    reg = by_name(name)
    raw = round(real_value * reg.scale)
    return max(0, min(65535, raw))


def decode(name: str, raw_value: int) -> float:
    """Convert a raw uint16 register value back into a real-world value."""
    reg = by_name(name)
    return raw_value / reg.scale