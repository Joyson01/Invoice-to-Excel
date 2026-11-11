import openpyxl

def validate_template(template_path: str) -> tuple[bool, str]:
    required_sheets = {"orders", "boxes", "invoice"}
    try:
        wb = openpyxl.load_workbook(template_path, read_only=True)
    except Exception as exc:
        return False, f"Could not be opened ({type(exc).__name__})"
        
    have = {n.strip().lower() for n in wb.sheetnames}
    missing = required_sheets - have
    if missing:
        return False, f"Missing sheets: {', '.join(missing)}"
    return True, ""
