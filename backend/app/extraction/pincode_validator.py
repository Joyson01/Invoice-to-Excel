import re

RE_PINCODE = re.compile(r"\b(\d{6})\b")

def extract_pincode(address: str) -> str:
    m = RE_PINCODE.search(address)
    return m.group(1) if m else ""
