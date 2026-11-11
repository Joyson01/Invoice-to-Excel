from app.extraction.phone_normalizer import clean_phone

def test_clean_phone():
    assert clean_phone("7356976268 /99953 23357") == ["7356976268", "9995323357"]
    assert clean_phone("+919876543210") == ["9876543210"]
    assert clean_phone("09876543210") == ["9876543210"]
