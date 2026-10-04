import json
from typing import Any, Dict

BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

def decode_base58_to_bytes(encoded_str: str) -> bytes:
    """
    Decodes a Base58 encoded string back to raw bytes.
    Matches LunaTV / Bitcoin Base58 specification.
    """
    s = encoded_str.strip()
    if not s:
        return b""
    
    int_val = 0
    for char in s:
        idx = BASE58_ALPHABET.find(char)
        if idx == -1:
            raise ValueError(f"Invalid Base58 character found: {char}")
        int_val = int_val * 58 + idx
    
    res = bytearray()
    while int_val > 0:
        res.append(int_val & 0xFF)
        int_val >>= 8
    res.reverse()
    
    # Preserve leading zeros encoded as '1'
    leading_ones = len(s) - len(s.lstrip("1"))
    return bytes([0] * leading_ones) + bytes(res)

def decode_base58_json(encoded_str: str) -> Dict[str, Any]:
    """
    Decodes Base58 string directly into a Python dictionary.
    """
    raw_bytes = decode_base58_to_bytes(encoded_str)
    text = raw_bytes.decode("utf-8")
    return json.loads(text)
