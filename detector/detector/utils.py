from typing import Optional, Tuple


def parse_sid(sid: str) -> Optional[Tuple[str, str, str, str]]:
    """Parse source identifiers in dot or underscore formats."""
    if not sid:
        return None

    cleaned = sid[5:] if sid.startswith("FDSN:") else sid

    if "_" in cleaned:
        parts = cleaned.split("_")
        if len(parts) >= 4:
            net, sta, loc = parts[:3]
            chan = "".join(parts[3:])
            return (net, sta, loc, chan) if chan else None
        return None

    if "." in cleaned:
        parts = cleaned.split(".")
        if len(parts) >= 4:
            net, sta, loc, chan = parts[:4]
            return (net, sta, loc, chan) if chan else None

    return None
