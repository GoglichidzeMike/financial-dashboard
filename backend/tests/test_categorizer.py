from app.services.categorizer import (
    extract_merchant_raw,
    infer_category_fallback,
    normalize_merchant_name,
)


def test_extract_merchant_raw_from_merchant_token() -> None:
    details = "Payment - Amount: GEL32.96; Merchant: Wolt, Tbilisi, 61 Agmashenebeli ave.; MCC:4215"
    raw = extract_merchant_raw(details, direction="expense")
    assert raw == "Wolt"


def test_extract_merchant_raw_from_payment_service() -> None:
    details = "Payment - Amount GEL50.00; Payment, 04/01/2026 , payment service, Magti Internet Services, subscriber Phone Number"
    raw = extract_merchant_raw(details, direction="expense")
    assert raw == "Magti Internet Services"


def test_normalize_merchant_name() -> None:
    assert normalize_merchant_name("Wolt") == "wolt"


def test_transfer_rows_force_internal_transfer_merchant() -> None:
    details = (
        "Incoming Transfer - Amount: GEL4,000.00; Sender: goglichidze mikaeli; "
        "Details: piradi gadaritskhva"
    )
    raw = extract_merchant_raw(details, direction="transfer")
    assert raw == "internal transfer"


def test_automatic_conversion_forces_internal_transfer_merchant() -> None:
    details = "Income - Amount USD5.99; Automatic conversion, rate: 2.748"
    raw = extract_merchant_raw(details, direction="income")
    assert raw == "internal transfer"


def test_infer_category_fallback_mcc_and_keywords() -> None:
    allowed = {"Food Delivery", "Income & Transfers", "Other"}
    assert infer_category_fallback("wolt", "4215", "expense", allowed) == "Food Delivery"
    assert infer_category_fallback("salary transfer", None, "income", allowed) == "Income & Transfers"
