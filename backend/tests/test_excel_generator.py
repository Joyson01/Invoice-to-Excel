import openpyxl
import pytest
from app.excel_generator import generate_excel


def test_template_requires_all_three_sheets(tmp_path, dummy_invoice):
    path = tmp_path / 'incomplete.xlsx'
    workbook = openpyxl.Workbook()
    workbook.active.title = 'Orders'
    workbook.save(path)
    with pytest.raises(ValueError, match='Template missing required sheets'):
        generate_excel([dummy_invoice], str(path), str(tmp_path))
