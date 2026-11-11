"""Conservative label matching: never borrow the value of the next field."""
import re

INVOICE_LABEL = r'(?:Tax\s*)?Invoice\s*(?:Number|No\.?|#)'
PO_LABEL = r'(?:PO\s*(?:No\.?|Number)|Purchase\s*Order(?:\s*(?:No\.?|Number))?|Customer\s*Order(?:\s*(?:No\.?|Number))?|Order\s*Number)'
BOX_LABEL = r'(?:No\.?\s*O[FE]\s*Boxes|Number\s*of\s*Boxes|Total\s*Boxes)'
FIELD_LABEL = re.compile(
    rf'{INVOICE_LABEL}|{PO_LABEL}|{BOX_LABEL}|'
    r'NET\s*BILL\s*AMOUNT|Invoice\s*Total|Total\s*Invoice\s*Value|Grand\s*Total|'
    r'(?:Receiver\s*)?(?:Name|Mobile|Phone|Email)|Contact\s*No\.?|Tel\.?\s*(?:No\.?)?|'
    r'GSTIN|Party\s*PAN|Date[d]?|Weight|Place\s*of\s*Supply|Reverse\s*Charge|'
    r'Narration|Billed\s*to|Shipped\s*to|Bill\s*to|Ship\s*to|Payment|Bank|'
    r'E-?\s*Way\s*Bill', re.I)


def label_values(text, label):
    pattern = re.compile(r'(?<!\w)' + label + r'(?![A-Za-z])', re.I)
    lines = text.splitlines()
    for index, line in enumerate(lines):
        for match in pattern.finditer(line):
            tail = line[match.end():].lstrip(' .:\t')
            # A new label is never a value, whether beside or below this label.
            next_label = FIELD_LABEL.search(tail)
            if next_label:
                tail = tail[:next_label.start()].strip()
                if not tail:
                    continue
            if not tail and index + 1 < len(lines):
                tail = lines[index + 1].strip()
                if FIELD_LABEL.search(tail):
                    continue
            if tail:
                yield tail.strip()


def identifier(text, label, warnings, field):
    candidates = set()
    for value in label_values(text, label):
        match = re.match(r'([A-Za-z0-9][A-Za-z0-9/_.-]*)(?=$|\s)', value)
        if match and any(c.isdigit() for c in match[1]):
            candidates.add(match[1])
    if len(candidates) > 1:
        warnings.append(f'Conflicting {field} values - left blank for review')
    return next(iter(candidates)) if len(candidates) == 1 else ''


def _amount_candidates(text, label):
    number = r'(?<![\w.,/-])\d+(?:,\d{2,3})*(?:\.\d{1,2})?(?![\w.,/-])'
    candidates = set()
    ambiguous = False
    for tail in label_values(text, label):
        matches = list(re.finditer(number, tail))
        if len(matches) > 1:
            marked = [m for m in matches if re.search(r'(?:Rs\.?|INR|₹|`|\$)\s*$', tail[:m.start()], re.I)]
            if len(marked) != 1:
                ambiguous = True
                continue
            matches = marked
        if len(matches) == 1:
            candidates.add(float(matches[0][0].replace(',', '')))
    return candidates, ambiguous


def invoice_amount(text, warnings):
    # An explicitly labelled invoice value is stronger evidence than a table
    # footer that may contain both a quantity and an amount.
    primary, primary_ambiguous = _amount_candidates(text,
        r'(?:NET\s*BILL\s*AMOUNT|Total\s*Invoice\s*Value|Invoice\s*Total|Amount\s*Payable)')
    grand, grand_ambiguous = _amount_candidates(text, r'Grand\s*Total')
    if primary or primary_ambiguous:
        candidates = primary | grand
        ambiguous = primary_ambiguous
    elif grand or grand_ambiguous:
        candidates, ambiguous = grand, grand_ambiguous
    else:
        candidates, ambiguous = _amount_candidates(text, r'(?:Net\s*Amount|Total\s*Amount)')
    if len(candidates) > 1 or ambiguous:
        warnings.append('Conflicting or ambiguous Invoice Amount values - left blank for review')
        return None
    return next(iter(candidates)) if len(candidates) == 1 else None
