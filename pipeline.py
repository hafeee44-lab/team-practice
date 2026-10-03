from datetime import date


def get_items():
    items = [
        {"name": "Paracetamol", "expiry": "2027-06-30", "qty": 120},
        {"name": "Ibuprofen", "expiry": "2027-09-15", "qty": 80},
        {"name": "Amoxicillin", "expiry": "2027-12-01", "qty": 45},
    ]
    for item in items:
        item["days_left"] = (date.fromisoformat(item["expiry"]) - date.today()).days
    return items
