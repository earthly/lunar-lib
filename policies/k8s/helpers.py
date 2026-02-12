"""Helper functions for K8s policy checks."""

import re
from typing import Optional


# Binary suffixes (powers of 1024)
_BIN_SUFFIXES = {
    "Ki": 1024,
    "Mi": 1024**2,
    "Gi": 1024**3,
    "Ti": 1024**4,
    "Pi": 1024**5,
    "Ei": 1024**6,
}

# Decimal suffixes (powers of 1000)
_DEC_SUFFIXES = {
    "K": 1000,
    "M": 1000**2,
    "G": 1000**3,
    "T": 1000**4,
    "P": 1000**5,
    "E": 1000**6,
}


def parse_cpu_millicores(value) -> Optional[float]:
    """
    Parse a Kubernetes CPU value and return millicores.

    Examples:
        "100m" -> 100.0
        "0.5" -> 500.0
        "1" -> 1000.0
        "500n" -> 0.0005

    Returns None if the value cannot be parsed.
    """
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value) * 1000.0  # cores -> millicores

    s = str(value).strip()
    match = re.fullmatch(r"([0-9]*\.?[0-9]+)\s*([num]?)", s)
    if not match:
        return None

    val = float(match.group(1))
    suffix = match.group(2)

    if suffix == "n":  # nanocores
        return val / 1_000_000.0
    if suffix == "u":  # microcores
        return val / 1_000.0
    if suffix == "m":  # millicores
        return val
    # No suffix = cores
    return val * 1000.0


def parse_mem_bytes(value) -> Optional[float]:
    """
    Parse a Kubernetes memory value and return bytes.

    Examples:
        "128Mi" -> 134217728.0
        "1Gi" -> 1073741824.0
        "500M" -> 500000000.0

    Returns None if the value cannot be parsed.
    """
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    s = str(value).strip()
    match = re.fullmatch(r"([0-9]*\.?[0-9]+)\s*([KMGTP]i|[KMGTPE])?B?", s)
    if not match:
        return None

    val = float(match.group(1))
    suffix = match.group(2)

    if not suffix:
        return val

    if suffix in _BIN_SUFFIXES:
        return val * _BIN_SUFFIXES[suffix]

    if suffix in _DEC_SUFFIXES:
        return val * _DEC_SUFFIXES[suffix]

    return None

