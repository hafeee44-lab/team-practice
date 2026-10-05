import csv
import io
import json
import os
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Union

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
DATA_FILE = os.path.join(DATA_DIR, "inventory.json")
TRANSACTIONS_FILE = os.path.join(DATA_DIR, "transactions.json")

DEFAULT_ITEMS = [
    {
        "id": "MED-001",
        "name": "Paracetamol",
        "category": "Analgesic",
        "expiry": "2026-10-20",
        "qty": 120,
        "min_qty": 50,
        "unit_price": 5.50,
    },
    {
        "id": "MED-002",
        "name": "Ibuprofen",
        "category": "NSAID",
        "expiry": "2026-11-15",
        "qty": 30,
        "min_qty": 40,
        "unit_price": 8.00,
    },
    {
        "id": "MED-003",
        "name": "Amoxicillin",
        "category": "Antibiotic",
        "expiry": "2026-09-30",
        "qty": 45,
        "min_qty": 30,
        "unit_price": 12.50,
    },
    {
        "id": "MED-004",
        "name": "Metformin",
        "category": "Antidiabetic",
        "expiry": "2027-12-01",
        "qty": 150,
        "min_qty": 60,
        "unit_price": 6.25,
    },
    {
        "id": "MED-005",
        "name": "Cetirizine",
        "category": "Antihistamine",
        "expiry": "2026-10-05",
        "qty": 15,
        "min_qty": 20,
        "unit_price": 4.75,
    },
]


# ==============================================================================
# 1. CORE DATA PERSISTENCE & CRUD PIPELINE
# ==============================================================================

def load_inventory() -> List[Dict[str, Any]]:
    """Loads inventory from JSON storage or initializes default data."""
    if not os.path.exists(DATA_FILE):
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(DATA_FILE, "w") as f:
            json.dump(DEFAULT_ITEMS, f, indent=2)
        return [item.copy() for item in DEFAULT_ITEMS]

    try:
        with open(DATA_FILE, "r") as f:
            items = json.load(f)
            # Ensure unit_price exists for all items
            for item in items:
                if "unit_price" not in item:
                    item["unit_price"] = 5.0
            return items
    except (json.JSONDecodeError, OSError):
        return [item.copy() for item in DEFAULT_ITEMS]


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
        item_copy["unit_price"] = float(item_copy.get("unit_price", 5.0))

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
    unit_price: float = 5.0,
) -> Dict[str, Any]:
    """Adds a new medicine item to the inventory and logs transaction."""
    items = load_inventory()
    new_id = f"MED-{len(items) + 1:03d}"
    new_item = {
        "id": new_id,
        "name": name.strip(),
        "category": category.strip(),
        "expiry": expiry.strip(),
        "qty": int(qty),
        "min_qty": int(min_qty),
        "unit_price": float(unit_price),
    }
    items.append(new_item)
    save_inventory(items)
    log_transaction(new_id, "CREATE", int(qty), f"Added new item {name}")
    return new_item


def update_stock(item_id: str, delta_qty: int, reason: str = "") -> bool:
    """Updates the stock quantity of a specific item by delta_qty and logs transaction."""
    items = load_inventory()
    updated = False
    action = "RESTOCK" if delta_qty > 0 else "DISPENSE"

    for item in items:
        if item["id"] == item_id:
            item["qty"] = max(0, item["qty"] + delta_qty)
            updated = True
            break

    if updated:
        save_inventory(items)
        log_transaction(item_id, action, delta_qty, reason or f"Stock adjusted by {delta_qty}")
    return updated


def delete_item(item_id: str, reason: str = "") -> bool:
    """Deletes an item from inventory by ID and logs transaction."""
    items = load_inventory()
    initial_len = len(items)
    items = [item for item in items if item["id"] != item_id]
    if len(items) < initial_len:
        save_inventory(items)
        log_transaction(item_id, "DELETE", 0, reason or "Item removed from inventory")
        return True
    return False


# ==============================================================================
# FEATURE 1: BATCH CSV IMPORT & EXPORT PIPELINE
# ==============================================================================

def import_inventory_from_csv(csv_data: Union[str, bytes]) -> Dict[str, Any]:
    """Imports medicine inventory from CSV content string or bytes.

    Expected columns: name, category, expiry, qty, min_qty (optional), unit_price (optional)
    """
    if isinstance(csv_data, bytes):
        csv_text = csv_data.decode("utf-8-sig", errors="ignore")
    else:
        csv_text = csv_data

    reader = csv.DictReader(io.StringIO(csv_text))
    items = load_inventory()
    existing_names = {i["name"].lower(): i for i in items}
    
    imported_count = 0
    updated_count = 0
    errors = []

    for row_idx, row in enumerate(reader, start=1):
        try:
            name = row.get("name", "").strip()
            if not name:
                errors.append(f"Row {row_idx}: Missing medicine name.")
                continue

            category = row.get("category", "General").strip() or "General"
            expiry = row.get("expiry", "").strip()
            # Validate date format YYYY-MM-DD
            date.fromisoformat(expiry)
            qty = int(row.get("qty", 0))
            min_qty = int(row.get("min_qty", 30))
            unit_price = float(row.get("unit_price", 5.0))

            if name.lower() in existing_names:
                existing_item = existing_names[name.lower()]
                existing_item["qty"] += qty
                existing_item["expiry"] = expiry
                existing_item["min_qty"] = min_qty
                existing_item["unit_price"] = unit_price
                updated_count += 1
            else:
                new_id = f"MED-{len(items) + 1:03d}"
                new_item = {
                    "id": new_id,
                    "name": name,
                    "category": category,
                    "expiry": expiry,
                    "qty": qty,
                    "min_qty": min_qty,
                    "unit_price": unit_price,
                }
                items.append(new_item)
                existing_names[name.lower()] = new_item
                imported_count += 1

        except Exception as e:
            errors.append(f"Row {row_idx}: {str(e)}")

    if imported_count > 0 or updated_count > 0:
        save_inventory(items)
        log_transaction(
            "SYSTEM",
            "CSV_IMPORT",
            imported_count + updated_count,
            f"CSV Import: {imported_count} new, {updated_count} updated",
        )

    return {
        "imported_count": imported_count,
        "updated_count": updated_count,
        "errors": errors,
        "total_processed": imported_count + updated_count,
    }


def export_inventory_to_csv(only_urgent: bool = False) -> str:
    """Exports inventory as CSV string. If only_urgent=True, exports only items needing action."""
    items = get_items()
    if only_urgent:
        items = [i for i in items if i["status"] in ["EXPIRED", "CRITICAL"] or i["is_low_stock"]]

    output = io.StringIO()
    fieldnames = ["id", "name", "category", "expiry", "qty", "min_qty", "unit_price", "days_left", "status", "is_low_stock"]
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for item in items:
        writer.writerow(item)
    return output.getvalue()


# ==============================================================================
# FEATURE 2: SMART RESTOCKING & PURCHASE ORDER PIPELINE
# ==============================================================================

def get_restock_recommendations(safety_multiplier: float = 1.5) -> Dict[str, Any]:
    """Generates automated restocking and purchase order recommendations."""
    items = get_items()
    reorder_list = []
    total_units_needed = 0
    total_estimated_cost = 0.0

    for item in items:
        min_qty = item.get("min_qty", 30)
        curr_qty = item["qty"]
        target_qty = int(min_qty * safety_multiplier)
        status = item["status"]

        # If expired, current stock is unusable (treated as 0 available)
        effective_stock = 0 if status == "EXPIRED" else curr_qty

        if effective_stock < min_qty or status in ["EXPIRED", "CRITICAL"]:
            needed = max(min_qty, target_qty - effective_stock)
            unit_price = float(item.get("unit_price", 5.0))
            cost = round(needed * unit_price, 2)

            priority = "URGENT" if status == "EXPIRED" or effective_stock == 0 else "HIGH" if status == "CRITICAL" else "MEDIUM"

            reorder_item = {
                "id": item["id"],
                "name": item["name"],
                "category": item["category"],
                "current_qty": curr_qty,
                "effective_usable_qty": effective_stock,
                "min_qty": min_qty,
                "suggested_order_qty": needed,
                "unit_price": unit_price,
                "estimated_cost": cost,
                "status": status,
                "priority": priority,
            }
            reorder_list.append(reorder_item)
            total_units_needed += needed
            total_estimated_cost += cost

    # Sort reorders by priority
    priority_order = {"URGENT": 1, "HIGH": 2, "MEDIUM": 3}
    reorder_list.sort(key=lambda x: priority_order.get(x["priority"], 4))

    return {
        "items_to_reorder": reorder_list,
        "total_items_to_order": len(reorder_list),
        "total_units_needed": total_units_needed,
        "total_estimated_cost": round(total_estimated_cost, 2),
    }


# ==============================================================================
# FEATURE 3: AUDIT TRAIL & TRANSACTION LOGGING PIPELINE
# ==============================================================================

def load_transactions() -> List[Dict[str, Any]]:
    """Loads audit transaction logs from JSON."""
    if not os.path.exists(TRANSACTIONS_FILE):
        return []
    try:
        with open(TRANSACTIONS_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def log_transaction(item_id: str, action: str, qty_change: int, reason: str = "") -> Dict[str, Any]:
    """Records an inventory activity event."""
    transactions = load_transactions()
    tx_entry = {
        "tx_id": f"TX-{len(transactions) + 1:04d}",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "item_id": item_id,
        "action": action,
        "qty_change": qty_change,
        "reason": reason,
    }
    transactions.append(tx_entry)
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(TRANSACTIONS_FILE, "w") as f:
        json.dump(transactions, f, indent=2)
    return tx_entry


def get_transaction_history(limit: int = 50, item_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Returns recent transaction logs, newest first."""
    transactions = load_transactions()
    if item_id:
        transactions = [t for t in transactions if t["item_id"] == item_id]
    transactions.sort(key=lambda t: t["timestamp"], reverse=True)
    return transactions[:limit]


# ==============================================================================
# FEATURE 4: ADVANCED MULTI-FILTER & SEARCH PIPELINE
# ==============================================================================

def search_items(
    query: str = "",
    status: Optional[str] = None,
    category: Optional[str] = None,
    is_low_stock: Optional[bool] = None,
    sort_by: str = "urgency",
) -> List[Dict[str, Any]]:
    """Advanced search and multi-facet filtering pipeline for inventory items."""
    items = get_items()
    q = query.strip().lower()

    filtered = []
    for item in items:
        # Text search across id, name, category
        if q and not (q in item["id"].lower() or q in item["name"].lower() or q in item["category"].lower()):
            continue
        # Status filter
        if status and item["status"] != status:
            continue
        # Category filter
        if category and item["category"] != category:
            continue
        # Low stock filter
        if is_low_stock is not None and item["is_low_stock"] != is_low_stock:
            continue
        filtered.append(item)

    # Sorting options
    if sort_by == "name":
        filtered.sort(key=lambda x: x["name"].lower())
    elif sort_by == "qty_asc":
        filtered.sort(key=lambda x: x["qty"])
    elif sort_by == "qty_desc":
        filtered.sort(key=lambda x: x["qty"], reverse=True)
    elif sort_by == "expiry":
        filtered.sort(key=lambda x: x["expiry"])
    else:  # default 'urgency'
        filtered.sort(key=lambda x: (x["alert_level"], x["days_left"]))

    return filtered


# ==============================================================================
# INVENTORY METRICS & AI CONTEXT PREPARATION
# ==============================================================================

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


def get_ai_inventory_context() -> str:
    """Formats current inventory metrics, alerts, and restock needs into structured Markdown context

    specifically designed to be passed to LLMs/AI features for Person B's AI assistant.
    """
    items = get_items()
    alerts = get_inventory_alerts()
    analytics = get_inventory_analytics()
    restock = get_restock_recommendations()

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
        "## Recommended Reorder & Restock Needs:",
        f"- Total Items Needing Restock: {restock['total_items_to_order']}",
        f"- Estimated Purchase Cost: ${restock['total_estimated_cost']:.2f}",
        f"- Total Units Needed: {restock['total_units_needed']} packs",
        "",
        "## Detailed Inventory List:",
    ]

    for item in items:
        lines.append(
            f"- [{item['id']}] {item['name']} | Category: {item['category']} | "
            f"Qty: {item['qty']} (Min: {item.get('min_qty', 30)}) | "
            f"Unit Price: ${item.get('unit_price', 5.0):.2f} | "
            f"Expiry: {item['expiry']} ({item['days_left']} days left) | Status: {item['status']}"
        )

    return "\n".join(lines)
