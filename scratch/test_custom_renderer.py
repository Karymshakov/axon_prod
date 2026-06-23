import sys
import os
import re

# Add backend to path so we can import apps.leads.services.booking_tools
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from apps.leads.services.booking_tools import _render_custom_template

def test_basic_rendering():
    template = "👤 Гость: {guest_name}\n📞 Телефон: {guest_phone}"
    vars = {"guest_name": "Данияр", "guest_phone": "0550600791"}
    result = _render_custom_template(template, vars)
    assert result == "👤 Гость: Данияр\n📞 Телефон: 0550600791", f"Got: {repr(result)}"
    print("test_basic_rendering: PASS")

def test_strip_empty_placeholders():
    template = "👤 Гость: {guest_name}\n📱 Telegram: {telegram_handle}\n📞 Телефон: {guest_phone}"
    vars = {"guest_name": "Данияр", "telegram_handle": "", "guest_phone": "0550600791"}
    result = _render_custom_template(template, vars)
    assert result == "👤 Гость: Данияр\n📞 Телефон: 0550600791", f"Got: {repr(result)}"
    print("test_strip_empty_placeholders: PASS")

def test_tree_prefix_adjustment():
    template = (
        "🗓 Детали проживания:\n"
        "  ├─ Заезд: {checkin_date}\n"
        "  ├─ Выезд: {checkout_date}\n"
        "  └─ Итого: {total_price}"
    )
    # Test case 1: all non-empty
    vars_all = {"checkin_date": "2026-06-24", "checkout_date": "2026-06-26", "total_price": "19000"}
    res_all = _render_custom_template(template, vars_all)
    expected_all = (
        "🗓 Детали проживания:\n"
        "  ├─ Заезд: 2026-06-24\n"
        "  ├─ Выезд: 2026-06-26\n"
        "  └─ Итого: 19000"
    )
    assert res_all == expected_all, f"Got: {repr(res_all)}"

    # Test case 2: last one empty (total_price), should adjust checkout_date prefix to corner
    vars_last_empty = {"checkin_date": "2026-06-24", "checkout_date": "2026-06-26", "total_price": ""}
    res_le = _render_custom_template(template, vars_last_empty)
    expected_le = (
        "🗓 Детали проживания:\n"
        "  ├─ Заезд: 2026-06-24\n"
        "  └─ Выезд: 2026-06-26"
    )
    assert res_le == expected_le, f"Got: {repr(res_le)}"
    print("test_tree_prefix_adjustment: PASS")

def test_dangling_headers_strip():
    template = (
        "👤 Гость: {guest_name}\n"
        "\n"
        "🗓 Детали проживания:\n"
        "  ├─ Заезд: {checkin_date}\n"
        "  └─ Выезд: {checkout_date}"
    )
    # If both checkin_date and checkout_date are empty, the header "🗓 Детали проживания:" should be stripped too.
    vars = {"guest_name": "Данияр", "checkin_date": "", "checkout_date": ""}
    result = _render_custom_template(template, vars)
    assert result == "👤 Гость: Данияр", f"Got: {repr(result)}"
    print("test_dangling_headers_strip: PASS")

def test_double_blank_lines_collapse():
    template = "Line 1\n\n\nLine 2\n\nLine 3\n\n\n"
    result = _render_custom_template(template, {})
    assert result == "Line 1\n\nLine 2\n\nLine 3", f"Got: {repr(result)}"
    print("test_double_blank_lines_collapse: PASS")

if __name__ == "__main__":
    test_basic_rendering()
    test_strip_empty_placeholders()
    test_tree_prefix_adjustment()
    test_dangling_headers_strip()
    test_double_blank_lines_collapse()
    print("ALL TESTS PASSED SUCCESSFULLY!")
