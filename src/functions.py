"""SQLite storage helpers for AIKA+.

This module contains database operations only. Voice tools are defined in main.py.
The database is created automatically at <project root>/data/aika.db.
"""

from datetime import date, datetime
from pathlib import Path
import sqlite3

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "aika.db"


def connect_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialise_database():
    with connect_db() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                note TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS stock_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item TEXT NOT NULL,
                quantity TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Pending',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS food_waste (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item TEXT NOT NULL,
                quantity TEXT NOT NULL,
                waste_date TEXT NOT NULL,
                details TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS checklist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'General',
                status TEXT NOT NULL DEFAULT 'Incomplete',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS equipment_faults (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                equipment TEXT NOT NULL,
                description TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Open',
                reported_at TEXT NOT NULL,
                resolved_at TEXT
            );

            CREATE TABLE IF NOT EXISTS shift_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chef_name TEXT NOT NULL,
                started_at TEXT NOT NULL,
                ended_at TEXT
            );
            """
        )


def now_text():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def add_note(note: str) -> str:
    note = note.strip()
    if not note:
        return "I need the note text before I can save it."
    with connect_db() as db:
        cursor = db.execute(
            "INSERT INTO notes (note, created_at) VALUES (?, ?)",
            (note, now_text()),
        )
        note_id = cursor.lastrowid
    return f"Saved note {note_id}: {note}"


def list_notes() -> str:
    with connect_db() as db:
        rows = db.execute("SELECT id, note FROM notes ORDER BY id").fetchall()
    if not rows:
        return "There are no saved notes."
    return "\n".join(f"{row['id']}. {row['note']}" for row in rows)


def remove_note(note_id: int) -> str:
    with connect_db() as db:
        cursor = db.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    return f"Removed note {note_id}." if cursor.rowcount else f"I couldn't find note {note_id}."


def add_stock_request(item: str, quantity: str) -> str:
    item, quantity = item.strip(), quantity.strip()
    if not item or not quantity:
        return "I need both the item and its quantity."
    with connect_db() as db:
        cursor = db.execute(
            "INSERT INTO stock_requests (item, quantity, status, created_at) VALUES (?, ?, 'Pending', ?)",
            (item, quantity, now_text()),
        )
        request_id = cursor.lastrowid
    return f"Added stock request {request_id}: {quantity} {item}, pending."


def list_stock_requests() -> str:
    with connect_db() as db:
        rows = db.execute(
            "SELECT id, item, quantity, status FROM stock_requests ORDER BY id"
        ).fetchall()
    if not rows:
        return "There are no stock requests."
    return "\n".join(
        f"{r['id']}. {r['quantity']} {r['item']} — {r['status']}" for r in rows
    )


def remove_stock_request(request_id: int) -> str:
    with connect_db() as db:
        cursor = db.execute("DELETE FROM stock_requests WHERE id = ?", (request_id,))
    return (
        f"Removed stock request {request_id}."
        if cursor.rowcount
        else f"I couldn't find stock request {request_id}."
    )


def mark_stock_ordered(request_id: int) -> str:
    with connect_db() as db:
        cursor = db.execute(
            "UPDATE stock_requests SET status = 'Ordered' WHERE id = ?", (request_id,)
        )
    return (
        f"Marked stock request {request_id} as ordered."
        if cursor.rowcount
        else f"I couldn't find stock request {request_id}."
    )


def record_food_waste(item: str, quantity: str, waste_date: str = "", details: str = "") -> str:
    item, quantity = item.strip(), quantity.strip()
    waste_date = (waste_date or date.today().isoformat()).strip()
    try:
        date.fromisoformat(waste_date)
    except ValueError:
        return "Please provide the date in YYYY-MM-DD format, or leave it blank for today."
    if not item or not quantity:
        return "I need both the wasted food and its quantity."
    with connect_db() as db:
        db.execute(
            "INSERT INTO food_waste (item, quantity, waste_date, details) VALUES (?, ?, ?, ?)",
            (item, quantity, waste_date, details.strip()),
        )
    return f"Recorded {quantity} of {item} as food waste for {waste_date}."


def list_food_waste(waste_date: str = "") -> str:
    waste_date = (waste_date or date.today().isoformat()).strip()
    try:
        date.fromisoformat(waste_date)
    except ValueError:
        return "Please provide the date in YYYY-MM-DD format."
    with connect_db() as db:
        rows = db.execute(
            "SELECT item, quantity, details FROM food_waste WHERE waste_date = ? ORDER BY id",
            (waste_date,),
        ).fetchall()
    if not rows:
        return f"No food waste was recorded for {waste_date}."
    lines = [f"Food waste for {waste_date}:"]
    for row in rows:
        suffix = f" ({row['details']})" if row["details"] else ""
        lines.append(f"- {row['quantity']} {row['item']}{suffix}")
    return "\n".join(lines)


def add_checklist_task(task: str, category: str = "General") -> str:
    task, category = task.strip(), (category or "General").strip()
    if not task:
        return "Please tell me what task to add."
    with connect_db() as db:
        cursor = db.execute(
            "INSERT INTO checklist (task, category, status, created_at) VALUES (?, ?, 'Incomplete', ?)",
            (task, category, now_text()),
        )
        task_id = cursor.lastrowid
    return f"Added {category} checklist task {task_id}: {task}."


def list_checklist(category: str = "", incomplete_only: bool = False) -> str:
    query = "SELECT id, task, category, status FROM checklist"
    conditions, params = [], []
    if category.strip():
        conditions.append("LOWER(category) = LOWER(?)")
        params.append(category.strip())
    if incomplete_only:
        conditions.append("status = 'Incomplete'")
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY id"
    with connect_db() as db:
        rows = db.execute(query, params).fetchall()
    if not rows:
        qualifier = "incomplete " if incomplete_only else ""
        return f"There are no {qualifier}checklist tasks matching that request."
    return "\n".join(
        f"{r['id']}. [{r['status']}] {r['category']}: {r['task']}" for r in rows
    )


def complete_checklist_task(task_id: int) -> str:
    with connect_db() as db:
        cursor = db.execute(
            "UPDATE checklist SET status = 'Complete' WHERE id = ?", (task_id,)
        )
    return (
        f"Marked checklist task {task_id} complete."
        if cursor.rowcount
        else f"I couldn't find checklist task {task_id}."
    )


def remove_checklist_task(task_id: int) -> str:
    with connect_db() as db:
        cursor = db.execute("DELETE FROM checklist WHERE id = ?", (task_id,))
    return (
        f"Removed checklist task {task_id}."
        if cursor.rowcount
        else f"I couldn't find checklist task {task_id}."
    )


def report_equipment_fault(equipment: str, description: str) -> str:
    equipment, description = equipment.strip(), description.strip()
    if not equipment or not description:
        return "Please provide the equipment name and a description of the fault."
    with connect_db() as db:
        cursor = db.execute(
            "INSERT INTO equipment_faults (equipment, description, status, reported_at) VALUES (?, ?, 'Open', ?)",
            (equipment, description, now_text()),
        )
        fault_id = cursor.lastrowid
    return f"Recorded equipment fault {fault_id}: {equipment} — {description}. Status: open."


def list_equipment_faults(open_only: bool = True) -> str:
    query = "SELECT id, equipment, description, status, reported_at FROM equipment_faults"
    if open_only:
        query += " WHERE status = 'Open'"
    query += " ORDER BY id"
    with connect_db() as db:
        rows = db.execute(query).fetchall()
    if not rows:
        return "There are no open equipment faults." if open_only else "There are no recorded equipment faults."
    return "\n".join(
        f"{r['id']}. {r['equipment']}: {r['description']} [{r['status']}]"
        for r in rows
    )


def resolve_equipment_fault(fault_id: int) -> str:
    with connect_db() as db:
        cursor = db.execute(
            "UPDATE equipment_faults SET status = 'Resolved', resolved_at = ? WHERE id = ? AND status = 'Open'",
            (now_text(), fault_id),
        )
    return (
        f"Marked equipment fault {fault_id} as resolved."
        if cursor.rowcount
        else f"I couldn't find an open equipment fault with ID {fault_id}."
    )


def start_shift(chef_name: str) -> str:
    chef_name = chef_name.strip()
    if not chef_name:
        return "Please tell me the chef's name."
    with connect_db() as db:
        db.execute("UPDATE shift_log SET ended_at = ? WHERE ended_at IS NULL", (now_text(),))
        cursor = db.execute(
            "INSERT INTO shift_log (chef_name, started_at) VALUES (?, ?)",
            (chef_name, now_text()),
        )
        shift_id = cursor.lastrowid
    return f"Shift {shift_id} started for Chef {chef_name}."


def current_chef() -> str:
    with connect_db() as db:
        row = db.execute(
            "SELECT chef_name, started_at FROM shift_log WHERE ended_at IS NULL ORDER BY id DESC LIMIT 1"
        ).fetchone()
    if not row:
        return "No chef has been identified for the current shift."
    return f"The current chef is {row['chef_name']}. Shift started at {row['started_at']}."


def calculate_portion(ingredient: str, amount: float, unit: str, base_servings: int, target_servings: int) -> str:
    if amount < 0 or base_servings <= 0 or target_servings <= 0:
        return "The amount must be zero or greater, and both serving counts must be greater than zero."
    result = amount * target_servings / base_servings
    return (
        f"For {target_servings} people, use {result:g} {unit} of {ingredient}, "
        f"scaled from {amount:g} {unit} for {base_servings} people."
    )


initialise_database()
