import json, os, sqlite3
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
        conn.execute("""CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
            description TEXT DEFAULT '', priority TEXT NOT NULL DEFAULT 'Medium',
            due_date TEXT DEFAULT '', status TEXT NOT NULL DEFAULT 'Pending',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")

def dataset_rows():
    if not DATASET.exists(): return []
    try:
        with DATASET.open(encoding="utf-8") as f: data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError): return []

@app.route("/")
def index():
    status, q = request.args.get("status", ""), request.args.get("q", "").strip()
    sql, args = "SELECT * FROM tasks WHERE 1=1", []
    if status in STATUSES:
        sql += " AND status=?"; args.append(status)
    if q:
        sql += " AND (title LIKE ? OR description LIKE ?)"; args += [f"%{q}%", f"%{q}%"]
    sql += " ORDER BY CASE priority WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END, due_date, id DESC"
    with db() as conn:
        tasks = conn.execute(sql, args).fetchall()
        counts = {s: conn.execute("SELECT COUNT(*) FROM tasks WHERE status=?", (s,)).fetchone()[0] for s in STATUSES}
    return render_template("index.html", tasks=tasks, counts=counts, statuses=STATUSES,
        priorities=PRIORITIES, selected_status=status, search=q, dataset_available=DATASET.exists())

@app.post("/tasks")
def add_task():
    title = request.form.get("title", "").strip()
    if not title:
        flash("Task title is required.", "error"); return redirect(url_for("index"))
    priority = request.form.get("priority", "Medium")
    if priority not in PRIORITIES: priority = "Medium"
    with db() as conn:
        conn.execute("INSERT INTO tasks(title,description,priority,due_date) VALUES(?,?,?,?)",
            (title, request.form.get("description","").strip(), priority, request.form.get("due_date","").strip()))
    flash("Task added.", "success"); return redirect(url_for("index"))

@app.route("/tasks/<int:task_id>/edit", methods=["GET","POST"])
def edit_task(task_id):
    with db() as conn:
        task = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if task is None: abort(404)
        if request.method == "POST":
            title = request.form.get("title","").strip()
            if not title:
                flash("Task title is required.", "error")
                return render_template("edit.html", task=task, priorities=PRIORITIES, statuses=STATUSES)
            priority, status = request.form.get("priority","Medium"), request.form.get("status","Pending")
            if priority not in PRIORITIES: priority = "Medium"
            if status not in STATUSES: status = "Pending"
            conn.execute("UPDATE tasks SET title=?,description=?,priority=?,due_date=?,status=? WHERE id=?",
                (title, request.form.get("description","").strip(), priority,
                 request.form.get("due_date","").strip(), status, task_id))
            flash("Task updated.", "success"); return redirect(url_for("index"))
    return render_template("edit.html", task=task, priorities=PRIORITIES, statuses=STATUSES)

@app.post("/tasks/<int:task_id>/complete")
def complete_task(task_id):
    with db() as conn: conn.execute("UPDATE tasks SET status='Completed' WHERE id=?", (task_id,))
    flash("Task marked completed.", "success"); return redirect(url_for("index"))

@app.post("/tasks/<int:task_id>/delete")
def delete_task(task_id):
    with db() as conn: conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
    flash("Task deleted.", "success"); return redirect(url_for("index"))

@app.route("/dataset")
def dataset():
    rows = dataset_rows()
    q = request.args.get("q","").strip().lower()
    if q: rows = [r for r in rows if q in str(r.get("TaskTitle","")).lower() or q in str(r.get("ListTitle","")).lower()]
    page = max(1, request.args.get("page",1,type=int)); per_page = 25
    total = len(rows)
    return render_template("dataset.html", rows=rows[(page-1)*per_page:page*per_page],
        total=total, page=page, pages=max(1,(total+per_page-1)//per_page),
        search=request.args.get("q",""), available=DATASET.exists())

@app.post("/dataset/import/<int:dataset_index>")
def import_dataset_task(dataset_index):
    rows = dataset_rows()
    if dataset_index < 0 or dataset_index >= len(rows): abort(404)
    row = rows[dataset_index]; title = str(row.get("TaskTitle","")).strip()
    if not title: flash("This entry has no task title.", "error"); return redirect(url_for("dataset"))
    desc = f"Imported from MS-LaTTE. Source list: {row.get('ListTitle','Not specified')}"
    with db() as conn: conn.execute("INSERT INTO tasks(title,description) VALUES(?,?)",(title,desc))
    flash("Dataset task added to your task list.", "success"); return redirect(url_for("index"))

@app.get("/health")
def health(): return {"status":"ok"}

init_db()
if __name__ == "__main__": app.run(host="0.0.0.0", port=5000)
