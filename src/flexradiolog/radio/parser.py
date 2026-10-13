"""SmartSDR TCP/IP API protocol parser."""

from dataclasses import dataclass, field
import re
from typing import Dict, Optional


@dataclass
class ParsedMessage:
    """Represents a parsed SmartSDR message."""
    raw: str
    msg_type: str  # 'V', 'H', 'R', 'S', 'M', or 'UNKNOWN'
    handle: Optional[str] = None
    seq: Optional[str] = None
    code: Optional[str] = None
    object_type: Optional[str] = None  # e.g., 'client', 'interlock', 'slice'
    object_id: Optional[str] = None  # e.g., client UUID or slice index
    attributes: Dict[str, str] = field(default_factory=dict)


def parse_key_value_pairs(text: str) -> Dict[str, str]:
    """Parse space-separated key=value pairs and boolean/status flags into a dictionary with lowercased keys."""
    attrs: Dict[str, str] = {}
    # Handles key=value and key="value with spaces"
    pattern = re.compile(r'([A-Za-z0-9_]+)=(?:"([^"]*)"|([^\s]+))')
    for match in pattern.finditer(text):
        key = match.group(1).lower()
        val = match.group(2) if match.group(2) is not None else match.group(3)
        attrs[key] = val or ""

    # Also capture standalone keywords if not already matched as key=value
    for word in text.split():
        if "=" not in word:
            w_lower = word.lower()
            if w_lower == "connected":
                attrs["connected"] = "1"
            elif w_lower == "disconnected":
                attrs["connected"] = "0"
            elif w_lower not in attrs:
                attrs[w_lower] = "1"

    return attrs


def parse_frequency_hz(val: str | float | int) -> int:
    """Parse frequency string into Hz integer. Supports MHz floats and Hz integers."""
    try:
        val_str = str(val).strip()
        if not val_str:
            return 0
        if "." in val_str:
            f = float(val_str)
            # If value is in MHz (e.g. 14.074000 or 7.1)
            if f < 2000.0:
                return int(round(f * 1_000_000))
            return int(round(f))
        
        num = int(val_str)
        # If in kHz (e.g. 14074)
        if 100 <= num < 1_000_000:
            return num * 1_000
        return num
    except (ValueError, TypeError):
        return 0


class ProtocolParser:
    """Parser for line-delimited SmartSDR text messages."""

    @staticmethod
    def parse_line(line: str) -> Optional[ParsedMessage]:
        """Parse a single line received from FlexRadio TCP port 4992."""
        raw = line.strip()
        if not raw:
            return None

        # Version line: V<version>
        if raw.startswith("V") and not raw.startswith("V|"):
            return ParsedMessage(
                raw=raw,
                msg_type="V",
                attributes={"version": raw[1:].strip()},
            )

        # Radio handle line: H<handle>
        if raw.startswith("H") and not raw.startswith("H|"):
            return ParsedMessage(
                raw=raw,
                msg_type="H",
                handle=raw[1:].strip(),
            )

        # Delimited lines: Prefix|Payload
        if "|" in raw:
            prefix, payload = raw.split("|", 1)
            prefix = prefix.strip()
            payload = payload.strip()

            # Command response: R<seq>|<return_code>|<message>
            if prefix.startswith("R"):
                parts = payload.split("|", 1)
                code = parts[0].strip() if parts else "0"
                msg = parts[1].strip() if len(parts) > 1 else ""
                return ParsedMessage(
                    raw=raw,
                    msg_type="R",
                    seq=prefix[1:].strip(),
                    code=code,
                    attributes={"message": msg},
                )

            # Status message: S<handle>|<type> [id] [k=v ...]
            if prefix.startswith("S"):
                handle = prefix[1:].strip()
                tokens = payload.split(None, 2)
                if not tokens:
                    return ParsedMessage(raw=raw, msg_type="S", handle=handle)

                obj_type = tokens[0].lower()
                obj_id: Optional[str] = None
                kv_string = ""

                if len(tokens) == 2:
                    if "=" in tokens[1] or tokens[1].lower() in ("connected", "disconnected"):
                        kv_string = tokens[1]
                    else:
                        obj_id = tokens[1]
                elif len(tokens) >= 3:
                    if "=" in tokens[1] or tokens[1].lower() in ("connected", "disconnected"):
                        # e.g., interlock state=TRANSMITTING ...
                        kv_string = f"{tokens[1]} {tokens[2]}"
                    else:
                        # e.g., client 0x4B28E780 connected ... or client 0B3B59D0-... connected=1 ...
                        obj_id = tokens[1]
                        kv_string = tokens[2]

                attrs = parse_key_value_pairs(kv_string)
                return ParsedMessage(
                    raw=raw,
                    msg_type="S",
                    handle=handle,
                    object_type=obj_type,
                    object_id=obj_id,
                    attributes=attrs,
                )

            # Message: M<code>|<text>
            if prefix.startswith("M"):
                code = prefix[1:].strip()
                attrs = {"message": payload}
                m = re.search(r'Client connected from IP\s+([0-9a-fA-F.:]+)', payload, re.IGNORECASE)
                if m:
                    attrs["ip"] = m.group(1)
                return ParsedMessage(
                    raw=raw,
                    msg_type="M",
                    code=code,
                    attributes=attrs,
                )

        return ParsedMessage(
            raw=raw,
            msg_type="UNKNOWN",
            attributes={"text": raw},
        )
