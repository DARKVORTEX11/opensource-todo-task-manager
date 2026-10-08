import json
import os
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from flask import Flask, abort, flash, redirect, render_template, request, url_for

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "development-only-change-me")

BASE = Path(__file__).resolve().parent
DATASET = BASE / "data" / "MS-LaTTE.json"
DB = Path(os.environ.get("DATABASE_PATH", BASE / "instance" / "tasks.db"))

STATUSES = ("Pending", "In Progress", "Completed")
PRIORITIES = ("Low", "Medium", "High")


def db():
    DB.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                priority TEXT NOT NULL DEFAULT 'Medium',
                due_date TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'Pending',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                completed_at TEXT DEFAULT ''
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                name TEXT DEFAULT ''
            )
        """)

        conn.execute("""
            INSERT OR IGNORE INTO user_settings (id, name)
            VALUES (1, '')
        """)

        # Upgrade an older database that doesn't have completed_at.
        columns = [
            row["name"]
            for row in conn.execute("PRAGMA table_info(tasks)").fetchall()
        ]

        if "completed_at" not in columns:
            conn.execute(
                "ALTER TABLE tasks ADD COLUMN completed_at TEXT DEFAULT ''"
            )


def dataset_rows():
    if not DATASET.exists():
        return []

    try:
        with DATASET.open(encoding="utf-8") as f:
            data = json.load(f)

        return data if isinstance(data, list) else []

    except (OSError, json.JSONDecodeError):
        return []


def get_user_name():
    with db() as conn:
        row = conn.execute(
            "SELECT name FROM user_settings WHERE id=1"
        ).fetchone()

    return row["name"].strip() if row and row["name"] else ""


def get_dashboard_data():
    today = date.today().isoformat()

    with db() as conn:
        tasks = conn.execute("""
            SELECT *
            FROM tasks
            ORDER BY
                CASE priority
                    WHEN 'High' THEN 1
                    WHEN 'Medium' THEN 2
                    ELSE 3
                END,
                CASE
                    WHEN due_date = ? THEN 0
                    WHEN due_date = '' THEN 2
                    ELSE 1
                END,
                due_date,
                id DESC
        """, (today,)).fetchall()

        today_tasks = conn.execute("""
            SELECT *
            FROM tasks
            WHERE due_date = ?
            ORDER BY
                CASE priority
                    WHEN 'High' THEN 1
                    WHEN 'Medium' THEN 2
                    ELSE 3
                END,
                id DESC
        """, (today,)).fetchall()

        counts = {
            status: conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE status=?",
                (status,)
            ).fetchone()[0]
            for status in STATUSES
        }

        total = conn.execute(
            "SELECT COUNT(*) FROM tasks"
        ).fetchone()[0]

    completed_percentage = (
        round((counts["Completed"] / total) * 100)
        if total
        else 0
    )

    return {
        "tasks": tasks,
        "today_tasks": today_tasks,
        "counts": counts,
        "total": total,
        "completed_percentage": completed_percentage,
    }


@app.context_processor
def inject_user():
    return {
        "user_name": get_user_name()
    }


@app.route("/")
def index():
    status = request.args.get("status", "")
    q = request.args.get("q", "").strip()

    data = get_dashboard_data()

    tasks = data["tasks"]

    if status in STATUSES:
        tasks = [task for task in tasks if task["status"] == status]

    if q:
        q_lower = q.lower()

        tasks = [
            task for task in tasks
            if q_lower in task["title"].lower()
            or q_lower in task["description"].lower()
        ]

    return render_template(
        "index.html",
        tasks=tasks,
        today_tasks=data["today_tasks"],
        counts=data["counts"],
        total=data["total"],
        completed_percentage=data["completed_percentage"],
        statuses=STATUSES,
        priorities=PRIORITIES,
        selected_status=status,
        search=q,
        dataset_available=DATASET.exists(),
        today=date.today().isoformat(),
    )


@app.post("/settings/name")
def save_name():
    name = request.form.get("name", "").strip()

    if not name:
        flash("Please enter your name.", "error")
        return redirect(url_for("index"))

    # Keep the UI clean and avoid extremely long names.
    name = name[:60]

    with db() as conn:
        conn.execute(
            "UPDATE user_settings SET name=? WHERE id=1",
            (name,)
        )

    flash(f"Welcome, {name}.", "success")
    return redirect(url_for("index"))


@app.post("/tasks")
def add_task():
    title = request.form.get("title", "").strip()

    if not title:
        flash("Task title is required.", "error")
        return redirect(url_for("index"))

    priority = request.form.get("priority", "Medium")

    if priority not in PRIORITIES:
        priority = "Medium"

    description = request.form.get("description", "").strip()
    due_date = request.form.get("due_date", "").strip()

    with db() as conn:
        conn.execute("""
            INSERT INTO tasks (
                title,
                description,
                priority,
                due_date
            )
            VALUES (?, ?, ?, ?)
        """, (
            title,
            description,
            priority,
            due_date
        ))

    flash("Task added.", "success")
    return redirect(url_for("index"))


@app.route("/tasks/<int:task_id>/edit", methods=["GET", "POST"])
def edit_task(task_id):
    with db() as conn:
        task = conn.execute(
            "SELECT * FROM tasks WHERE id=?",
            (task_id,)
        ).fetchone()

        if task is None:
            abort(404)

        if request.method == "POST":
            title = request.form.get("title", "").strip()

            if not title:
                flash("Task title is required.", "error")

                return render_template(
                    "edit.html",
                    task=task,
                    priorities=PRIORITIES,
                    statuses=STATUSES
                )

            priority = request.form.get("priority", "Medium")
            status = request.form.get("status", "Pending")

            if priority not in PRIORITIES:
                priority = "Medium"

            if status not in STATUSES:
                status = "Pending"

            due_date = request.form.get("due_date", "").strip()
            description = request.form.get("description", "").strip()

            completed_at = task["completed_at"]

            if status == "Completed":
                if not completed_at:
                    completed_at = date.today().isoformat()
            else:
                completed_at = ""

            conn.execute("""
                UPDATE tasks
                SET
                    title=?,
                    description=?,
                    priority=?,
                    due_date=?,
                    status=?,
                    completed_at=?
                WHERE id=?
            """, (
                title,
                description,
                priority,
                due_date,
                status,
                completed_at,
                task_id
            ))

            flash("Task updated.", "success")
            return redirect(url_for("index"))

    return render_template(
        "edit.html",
        task=task,
        priorities=PRIORITIES,
        statuses=STATUSES
    )


@app.post("/tasks/<int:task_id>/complete")
def complete_task(task_id):
    with db() as conn:
        conn.execute("""
            UPDATE tasks
            SET
                status='Completed',
                completed_at=?
            WHERE id=?
        """, (
            date.today().isoformat(),
            task_id
        ))

    flash("Task marked completed.", "success")
    return redirect(url_for("index"))


@app.post("/tasks/<int:task_id>/delete")
def delete_task(task_id):
    with db() as conn:
        conn.execute(
            "DELETE FROM tasks WHERE id=?",
            (task_id,)
        )

    flash("Task deleted.", "deleted")
    return redirect(url_for("index"))


@app.route("/performance")
def performance():
    today = date.today()

    labels = []
    completed = []
    pending = []
    in_progress = []

    with db() as conn:
        for offset in range(13, -1, -1):
            current_day = today - timedelta(days=offset)
            current_iso = current_day.isoformat()

            labels.append(
                current_day.strftime("%d %b")
            )

            completed_count = conn.execute("""
                SELECT COUNT(*)
                FROM tasks
                WHERE status='Completed'
                AND completed_at=?
            """, (current_iso,)).fetchone()[0]

            pending_count = conn.execute("""
                SELECT COUNT(*)
                FROM tasks
                WHERE status='Pending'
                AND due_date=?
            """, (current_iso,)).fetchone()[0]

            progress_count = conn.execute("""
                SELECT COUNT(*)
                FROM tasks
                WHERE status='In Progress'
                AND due_date=?
            """, (current_iso,)).fetchone()[0]

            completed.append(completed_count)
            pending.append(pending_count)
            in_progress.append(progress_count)

        counts = {
            status: conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE status=?",
                (status,)
            ).fetchone()[0]
            for status in STATUSES
        }

        total = conn.execute(
            "SELECT COUNT(*) FROM tasks"
        ).fetchone()[0]

    completion_rate = (
        round((counts["Completed"] / total) * 100)
        if total
        else 0
    )

    chart_data = {
        "labels": labels,
        "completed": completed,
        "pending": pending,
        "in_progress": in_progress,
    }

    return render_template(
        "performance.html",
        chart_data=chart_data,
        counts=counts,
        total=total,
        completion_rate=completion_rate,
    )


@app.route("/dataset")
def dataset():
    rows = dataset_rows()

    original_search = request.args.get("q", "")
    q = original_search.strip().lower()

    if q:
        rows = [
            row
            for row in rows
            if q in str(row.get("TaskTitle", "")).lower()
            or q in str(row.get("ListTitle", "")).lower()
        ]

    page = max(
        1,
        request.args.get("page", 1, type=int)
    )

    per_page = 25
    total = len(rows)

    pages = max(
        1,
        (total + per_page - 1) // per_page
    )

    if page > pages:
        page = pages

    start = (page - 1) * per_page
    end = start + per_page

    return render_template(
        "dataset.html",
        rows=rows[start:end],
        total=total,
        page=page,
        pages=pages,
        search=original_search,
        available=DATASET.exists(),
    )


@app.post("/dataset/import/<int:dataset_index>")
def import_dataset_task(dataset_index):
    rows = dataset_rows()

    if dataset_index < 0 or dataset_index >= len(rows):
        abort(404)

    row = rows[dataset_index]

    title = str(
        row.get("TaskTitle", "")
    ).strip()

    if not title:
        flash(
            "This entry has no task title.",
            "error"
        )
        return redirect(url_for("dataset"))

    desc = (
        "Imported from MS-LaTTE. "
        f"Source list: {row.get('ListTitle', 'Not specified')}"
    )

    with db() as conn:
        conn.execute("""
            INSERT INTO tasks (
                title,
                description
            )
            VALUES (?, ?)
        """, (
            title,
            desc
        ))

    flash(
        "Dataset task added to your task list.",
        "success"
    )

    return redirect(url_for("index"))


@app.get("/health")
def health():
    return {"status": "ok"}


init_db()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )