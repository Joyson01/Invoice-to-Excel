import re

def clean_phone(raw: str) -> list[str]:
    """'7356976268 /99953 23357' -> ['7356976268', '9995323357']"""
    out: list[str] = []
    for chunk in re.split(r"[/,;|]| {2,}", raw):
        digits = re.sub(r"\D", "", chunk)
        if digits.startswith("+91"):
            digits = digits[3:]
        elif digits.startswith("91") and len(digits) == 12:
            digits = digits[2:]
        if digits.startswith("0") and len(digits) == 11:
            digits = digits[1:]
        if len(digits) == 10 and digits not in out:
            out.append(digits)
    if not out:  # fall back: strip everything and window 10-digit runs
        digits = re.sub(r"\D", "", raw)
        for i in range(0, max(1, len(digits) - 9), 10):
            d = digits[i:i + 10]
            if len(d) == 10 and d not in out:
                out.append(d)
    return out
