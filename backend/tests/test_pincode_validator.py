from app.extraction.pincode_validator import extract_pincode

def test_extract_pincode():
    assert extract_pincode("Some address 123456 here") == "123456"
    assert extract_pincode("No pincode here") == ""
