import json
import os
from datetime import date
from typing import Any, Dict, List, Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
DATA_FILE = os.path.join(DATA_DIR, "inventory.json")

DEFAULT_ITEMS = [
    {
        "id": "MED-001",
        "name": "Paracetamol",
        "category": "Analgesic",
        "expiry": "2026-10-20",
        "qty": 120,
        "min_qty": 50,
    },
    {
        "id": "MED-002",
        "name": "Ibuprofen",
        "category": "NSAID",
        "expiry": "2026-11-15",
        "qty": 30,
        "min_qty": 40,
    },
    {
        "id": "MED-003",
        "name": "Amoxicillin",
        "category": "Antibiotic",
        "expiry": "2026-09-30",
        "qty": 45,
        "min_qty": 30,
    },
    {
        "id": "MED-004",
        "name": "Metformin",
        "category": "Antidiabetic",
        "expiry": "2027-12-01",
        "qty": 150,
        "min_qty": 60,
    },
    {
        "id": "MED-005",
        "name": "Cetirizine",
        "category": "Antihistamine",
        "expiry": "2026-10-05",
        "qty": 15,
        "min_qty": 20,
    },
]


def load_inventory() -> List[Dict[str, Any]]:
    """Loads inventory from JSON storage or initializes default data."""
    if not os.path.exists(DATA_FILE):
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(DATA_FILE, "w") as f:
            json.dump(DEFAULT_ITEMS, f, indent=2)
        return DEFAULT_ITEMS.copy()

    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return DEFAULT_ITEMS.copy()


def save_inventory(items: List[Dict[str, Any]]) -> None:
    """Saves inventory list to JSON storage."""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(items, f, indent=2)


def get_items(
    category_filter: Optional[str] = None, status_filter: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Fetches inventory items enriched with expiry days, alert status, and low stock flags."""
    raw_items = load_inventory()
    enriched = []
    today = date.today()

    for item in raw_items:
        item_copy = item.copy()
        expiry_date = date.fromisoformat(item_copy["expiry"])
        days_left = (expiry_date - today).days
        item_copy["days_left"] = days_left

        min_qty = item_copy.get("min_qty", 30)
        item_copy["is_low_stock"] = item_copy["qty"] <= min_qty

        # Determine expiry alert status
        if days_left < 0:
            item_copy["status"] = "EXPIRED"
            item_copy["alert_level"] = 1  # Most urgent
        elif days_left <= 30:
            item_copy["status"] = "CRITICAL"
            item_copy["alert_level"] = 2
        elif days_left <= 90:
            item_copy["status"] = "WARNING"
            item_copy["alert_level"] = 3
        else:
            item_copy["status"] = "GOOD"
            item_copy["alert_level"] = 4

        # Filtering logic
        if category_filter and item_copy.get("category") != category_filter:
            continue
        if status_filter and item_copy.get("status") != status_filter:
            continue

        enriched.append(item_copy)

    # Sort by urgency (alert level first, then days left)
    enriched.sort(key=lambda x: (x["alert_level"], x["days_left"]))
    return enriched


def add_item(
    name: str,
    category: str,
    expiry: str,
    qty: int,
    min_qty: int = 30,
) -> Dict[str, Any]:
    """Adds a new medicine item to the inventory."""
    items = load_inventory()
    new_id = f"MED-{len(items) + 1:03d}"
    new_item = {
        "id": new_id,
        "name": name.strip(),
        "category": category.strip(),
        "expiry": expiry.strip(),
        "qty": int(qty),
        "min_qty": int(min_qty),
    }
    items.append(new_item)
    save_inventory(items)
    return new_item


def update_stock(item_id: str, delta_qty: int) -> bool:
    """Updates the stock quantity of a specific item by delta_qty."""
    items = load_inventory()
    updated = False
    for item in items:
        if item["id"] == item_id:
            item["qty"] = max(0, item["qty"] + delta_qty)
            updated = True
            break

    if updated:
        save_inventory(items)
    return updated


def delete_item(item_id: str) -> bool:
    """Deletes an item from inventory by ID."""
    items = load_inventory()
    initial_len = len(items)
    items = [item for item in items if item["id"] != item_id]
    if len(items) < initial_len:
        save_inventory(items)
        return True
    return False


# Feature 1: Inventory & Expiry Alert Pipeline
def get_inventory_alerts() -> Dict[str, Any]:
    """Generates comprehensive inventory health and alert metrics."""
    items = get_items()
    expired = [i for i in items if i["status"] == "EXPIRED"]
    critical = [i for i in items if i["status"] == "CRITICAL"]
    warning = [i for i in items if i["status"] == "WARNING"]
    low_stock = [i for i in items if i["is_low_stock"]]

    urgent_action_required = [
        i for i in items if i["status"] in ["EXPIRED", "CRITICAL"] or i["is_low_stock"]
    ]

    return {
        "total_items": len(items),
        "total_packs": sum(i["qty"] for i in items),
        "expired_count": len(expired),
        "critical_count": len(critical),
        "warning_count": len(warning),
        "low_stock_count": len(low_stock),
        "urgent_action_count": len(urgent_action_required),
        "urgent_items": urgent_action_required,
    }


# Feature 2: Category & Risk Analytics Pipeline
def get_inventory_analytics() -> Dict[str, Any]:
    """Computes distribution, risk indices, and category breakdowns."""
    items = get_items()
    categories: Dict[str, int] = {}
    status_counts: Dict[str, int] = {
        "EXPIRED": 0,
        "CRITICAL": 0,
        "WARNING": 0,
        "GOOD": 0,
    }

    for item in items:
        cat = item.get("category", "General")
        categories[cat] = categories.get(cat, 0) + item["qty"]
        st = item["status"]
        status_counts[st] = status_counts.get(st, 0) + 1

    total = len(items)
    risk_score = 0.0
    if total > 0:
        # Risk score calculation (0 to 100) based on weighted non-good items
        weighted_risk = (
            (status_counts["EXPIRED"] * 1.0)
            + (status_counts["CRITICAL"] * 0.7)
            + (status_counts["WARNING"] * 0.3)
        )
        risk_score = min(100.0, round((weighted_risk / total) * 100, 1))

    return {
        "category_distribution": categories,
        "status_distribution": status_counts,
        "inventory_risk_score": risk_score,
    }


# Feature 3: AI Context Preparation Pipeline
def get_ai_inventory_context() -> str:
    """Formats current inventory metrics and warnings into structured Markdown context

    specifically designed to be passed to LLMs/AI features for person B's AI assistant.
    """
    items = get_items()
    alerts = get_inventory_alerts()
    analytics = get_inventory_analytics()

    lines = [
        "# DawaaWatch Current Inventory System Context",
        f"- Date: {date.today().isoformat()}",
        f"- Total Items Tracked: {alerts['total_items']}",
        f"- Total Packs in Stock: {alerts['total_packs']}",
        f"- Overall Inventory Risk Score: {analytics['inventory_risk_score']}/100",
        "",
        "## Urgent Alerts & Issues:",
        f"- Expired Medicines: {alerts['expired_count']} item(s)",
        f"- Critical Expiry (<30 days): {alerts['critical_count']} item(s)",
        f"- Warning Expiry (30-90 days): {alerts['warning_count']} item(s)",
        f"- Low Stock Medicines: {alerts['low_stock_count']} item(s)",
        "",
        "## Detailed Inventory List:",
    ]

    for item in items:
        lines.append(
            f"- [{item['id']}] {item['name']} | Category: {item['category']} | "
            f"Qty: {item['qty']} (Min: {item.get('min_qty', 30)}) | "
            f"Expiry: {item['expiry']} ({item['days_left']} days left) | Status: {item['status']}"
        )

    return "\n".join(lines)
