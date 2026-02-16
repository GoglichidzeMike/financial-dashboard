from datetime import date
from decimal import Decimal
from io import BytesIO

from openpyxl import Workbook

from app.services.parser import (
    compute_dedup_key,
    infer_direction,
    parse_decimal_value,
    parse_statement_xlsx,
)


def _build_workbook(rows: list[list[object]]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Statement"

    ws.append(["Date", "Details", "GEL", "USD", "EUR", "GBP"])
    for row in rows:
        ws.append(row)

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_parse_payment_row_with_mcc_card_posted_date() -> None:
    data = _build_workbook(
        [
            [
                "01/01/2026",
                "Payment - Amount: GEL2.95; Merchant: Nikora; MCC:5411; Date: 31/12/2025 15:25; Card No: ****5054",
                "-3,0",
                None,
                None,
                None,
            ]
        ]
    )

    result = parse_statement_xlsx(data)

    assert result.rows_total == 1
    assert result.rows_invalid == 0
    assert len(result.transactions) == 1

    tx = result.transactions[0]
    assert tx.direction == "expense"
    assert tx.date == date(2026, 1, 1)
    assert tx.posted_date == date(2025, 12, 31)
    assert tx.currency_original == "GEL"
    assert tx.amount_original == Decimal("2.95")
    assert tx.amount_gel == Decimal("3.00")
    assert tx.mcc_code == "5411"
    assert tx.card_last4 == "5054"


def test_parse_income_automatic_conversion_row() -> None:
    data = _build_workbook(
        [
            [
                "02/01/2026",
                "Income - Amount USD5.99; Automatic conversion, rate: 2.748",
                None,
                "6,0",
                None,
                None,
            ]
        ]
    )

    result = parse_statement_xlsx(data)
    tx = result.transactions[0]

    assert tx.direction == "income"
    assert tx.currency_original == "USD"
    assert tx.amount_original == Decimal("5.99")
    assert tx.conversion_rate == Decimal("2.748")
    assert tx.amount_gel == Decimal("16.46")


def test_skip_balance_row() -> None:
    data = _build_workbook(
        [
            ["Balance", "", "788,5", "0,0", "0,0", "0,0"],
            ["03/01/2026", "Payment - Amount GEL2.75", "-2,8", None, None, None],
        ]
    )

    result = parse_statement_xlsx(data)

    assert result.rows_total == 2
    assert result.rows_skipped_non_transaction == 1
    assert len(result.transactions) == 1


def test_parse_number_with_nbsp_and_comma_decimal() -> None:
    assert parse_decimal_value("4\u00a0000,0") == Decimal("4000.0")


def test_direction_mapping_payment_income_transfer() -> None:
    assert infer_direction("Payment - Amount GEL10.00") == "expense"
    assert infer_direction("Income - Amount USD1.00") == "income"
    assert infer_direction("Incoming Transfer - Amount GEL100.00") == "transfer"


def test_dedup_key_stability_same_input_same_hash() -> None:
    d = date(2026, 1, 1)
    a = Decimal("2.95")
    desc = "  Payment   - Amount: GEL2.95; Merchant: Nikora  "

    key1 = compute_dedup_key(d, a, desc)
    key2 = compute_dedup_key(d, Decimal("2.950"), "Payment - Amount: GEL2.95; Merchant: Nikora")

    assert key1 == key2


def test_invalid_row_counted_not_crashing_batch() -> None:
    data = _build_workbook(
        [
            ["INVALID", "Payment - Amount GEL2.75", "-2,8", None, None, None],
            ["03/01/2026", "Payment - Amount GEL1.00", "-1,0", None, None, None],
        ]
    )

    result = parse_statement_xlsx(data)

    assert result.rows_total == 2
    assert result.rows_invalid == 1
    assert len(result.transactions) == 1
