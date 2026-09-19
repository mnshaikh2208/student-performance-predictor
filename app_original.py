from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import sqlite3
import joblib
import pandas as pd
import os
import csv
import io
import logging
import secrets
from functools import wraps
from collections import OrderedDict
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("student-predictor")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(16))

DB = "student_predictor.db"
MODEL = "model.pkl"
FEATURES = ["study_hours", "attendance", "previous_marks", "assignments", "sleep_hours"]

# CHANGE THIS before sharing or deploying the project.
# Set it via an environment variable instead of editing this file where possible:
#   Windows (PowerShell):  $env:ADMIN_PASSWORD = "yourpassword"
#   macOS/Linux:           export ADMIN_PASSWORD="yourpassword"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

try:
    model = joblib.load(MODEL)
    log.info("Model loaded from %s", MODEL)
except FileNotFoundError:
    model = None
    log.warning("model.pkl not found — run train_model.py before predicting.")

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = db()
    con.execute("""
    CREATE TABLE IF NOT EXISTS predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_name TEXT NOT NULL,
        study_hours REAL NOT NULL,
        attendance REAL NOT NULL,
        previous_marks REAL NOT NULL,
        assignments INTEGER NOT NULL,
        sleep_hours REAL NOT NULL,
        prediction TEXT NOT NULL,
        confidence REAL,
        created_at TEXT NOT NULL
    )
    """)
    con.commit()
    con.close()

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return wrapper

@app.route("/")
def home():
    return render_template("index.html", model_loaded=model is not None)

@app.route("/history")
def history():
    PER_PAGE = 15
    page = request.args.get("page", 1, type=int)
    if page < 1:
        page = 1

    con = db()
    total = con.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
    total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    page = min(page, total_pages)

    rows = con.execute(
        "SELECT * FROM predictions ORDER BY id DESC LIMIT ? OFFSET ?",
        (PER_PAGE, (page - 1) * PER_PAGE)
    ).fetchall()
    con.close()

    return render_template(
        "history.html", rows=rows, total=total,
        page=page, total_pages=total_pages
    )

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/help")
def help_page():
    return render_template("help.html")

@app.get("/api/stats")
def stats():
    con = db()
    rows = con.execute(
        "SELECT prediction, study_hours, attendance, previous_marks, "
        "assignments, sleep_hours, created_at FROM predictions ORDER BY id"
    ).fetchall()
    con.close()

    total = len(rows)
    pass_count = sum(1 for r in rows if r["prediction"] == "Pass")
    fail_count = total - pass_count

    trend = OrderedDict()
    for r in rows:
        day = r["created_at"].split(" ")[0]
        trend.setdefault(day, {"Pass": 0, "Fail": 0})
        trend[day][r["prediction"]] += 1

    averages = {f: 0 for f in FEATURES}
    if total:
        for f in FEATURES:
            averages[f] = round(sum(r[f] for r in rows) / total, 2)

    importance = {}
    if model is not None and hasattr(model, "feature_importances_"):
        importance = {
            f: round(float(v), 4)
            for f, v in zip(FEATURES, model.feature_importances_)
        }

    return jsonify({
        "total": total,
        "pass_count": pass_count,
        "fail_count": fail_count,
        "trend": trend,
        "averages": averages,
        "feature_importance": importance
    })

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["is_admin"] = True
            return redirect(url_for("admin_panel"))
        error = "Incorrect password."
    return render_template("admin_login.html", error=error)

@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("admin_login"))

@app.route("/admin")
@login_required
def admin_panel():
    con = db()
    rows = con.execute("SELECT * FROM predictions ORDER BY id DESC").fetchall()
    con.close()
    total = len(rows)
    pass_count = sum(1 for r in rows if r["prediction"] == "Pass")
    fail_count = total - pass_count
    return render_template(
        "admin.html", rows=rows, total=total,
        pass_count=pass_count, fail_count=fail_count
    )

@app.post("/admin/delete/<int:pred_id>")
@login_required
def admin_delete(pred_id):
    con = db()
    con.execute("DELETE FROM predictions WHERE id = ?", (pred_id,))
    con.commit()
    con.close()
    log.info("Admin deleted prediction id=%s", pred_id)
    return redirect(url_for("admin_panel"))

@app.get("/admin/export")
@login_required
def admin_export():
    con = db()
    rows = con.execute("SELECT * FROM predictions ORDER BY id DESC").fetchall()
    con.close()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(rows[0].keys() if rows else [
        "id", "student_name", "study_hours", "attendance", "previous_marks",
        "assignments", "sleep_hours", "prediction", "confidence", "created_at"
    ])
    for r in rows:
        writer.writerow(tuple(r))

    return app.response_class(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=predictions_export.csv"}
    )

@app.get("/health")
def health():
    return jsonify({
        "status": "ok",
        "model_loaded": model is not None,
        "time": datetime.now().isoformat()
    })

@app.post("/api/predict")
def predict():
    if model is None:
        return jsonify({
            "error": "Model not found. Run 'python train_model.py' first to create model.pkl."
        }), 503
    try:
        d = request.get_json()
        name = str(d["student_name"]).strip()
        study = float(d["study_hours"])
        attendance = float(d["attendance"])
        marks = float(d["previous_marks"])
        assignments = int(d["assignments"])
        sleep = float(d["sleep_hours"])

        if not name:
            raise ValueError("Enter the student's name.")
        if not 0 <= study <= 24:
            raise ValueError("Study hours must be between 0 and 24.")
        if not 0 <= attendance <= 100:
            raise ValueError("Attendance must be between 0 and 100.")
        if not 0 <= marks <= 100:
            raise ValueError("Previous marks must be between 0 and 100.")
        if assignments < 0:
            raise ValueError("Assignments cannot be negative.")
        if not 0 <= sleep <= 24:
            raise ValueError("Sleep hours must be between 0 and 24.")

        X = pd.DataFrame([{
            "study_hours": study,
            "attendance": attendance,
            "previous_marks": marks,
            "assignments": assignments,
            "sleep_hours": sleep
        }])
        prediction = model.predict(X)[0]

        confidence = None
        if hasattr(model, "predict_proba"):
            confidence = round(float(max(model.predict_proba(X)[0])) * 100, 1)

        con = db()
        con.execute("""
            INSERT INTO predictions
            (student_name, study_hours, attendance, previous_marks,
             assignments, sleep_hours, prediction, confidence, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            name, study, attendance, marks, assignments,
            sleep, prediction, confidence,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        con.commit()
        con.close()

        return jsonify({
            "prediction": prediction,
            "confidence": confidence
        })

    except (KeyError, TypeError, ValueError) as e:
        log.info("Prediction rejected: %s", e)
        return jsonify({"error": str(e)}), 400
    except Exception:
        log.exception("Unexpected error during prediction")
        return jsonify({"error": "Something went wrong. Please try again."}), 500

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
