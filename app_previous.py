import os, sqlite3, joblib, io
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "student_performance.db")
MODEL_PATH = os.path.join(BASE_DIR, "model.pkl")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "student-performance-dev-key-change-me")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        course TEXT DEFAULT '',
        semester TEXT DEFAULT '',
        roll_no TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS academic_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        study_hours_per_day REAL NOT NULL,
        total_study_hours REAL NOT NULL,
        total_assignments INTEGER NOT NULL,
        completed_assignments INTEGER NOT NULL,
        pending_assignments INTEGER NOT NULL,
        attendance REAL NOT NULL,
        previous_marks REAL NOT NULL,
        sleep_hours REAL NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        academic_id INTEGER,
        prediction TEXT NOT NULL,
        confidence REAL NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    """)
    conn.commit()
    conn.close()

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

@app.context_processor
def inject_user():
    user = None
    if "user_id" in session:
        conn = get_db()
        user = conn.execute(
            "SELECT id,name,email,course,semester,roll_no FROM users WHERE id=?",
            (session["user_id"],)
        ).fetchone()
        conn.close()
    return {"current_user": user}

def predict_performance(study_hours, attendance, previous_marks, completed_assignments, sleep_hours):
    model = None
    if os.path.exists(MODEL_PATH):
        try:
            model = joblib.load(MODEL_PATH)
        except Exception:
            pass

    features = [[study_hours, attendance, previous_marks, completed_assignments, sleep_hours]]

    if model is not None:
        prediction = str(model.predict(features)[0])
        confidence = float(max(model.predict_proba(features)[0]) * 100) if hasattr(model, "predict_proba") else 85.0
        return prediction, round(confidence, 1)

    score = (
        min(study_hours / 8, 1) * 20 +
        (attendance / 100) * 25 +
        (previous_marks / 100) * 30 +
        min(completed_assignments / 10, 1) * 15 +
        min(sleep_hours / 8, 1) * 10
    )
    prediction = "Pass" if score >= 55 else "Fail"
    confidence = max(50, min(99, round(score if prediction == "Pass" else 100-score, 1)))
    return prediction, confidence

@app.route("/")
def index():
    return redirect(url_for("dashboard")) if "user_id" in session else render_template("index.html")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/help")
def help_page():
    return render_template("help.html")

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        from werkzeug.security import generate_password_hash
        name = request.form.get("name","").strip()
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        course = request.form.get("course","").strip()
        semester = request.form.get("semester","").strip()
        roll_no = request.form.get("roll_no","").strip()
        if not name or not email or not password:
            flash("Name, email and password are required.", "error")
            return render_template("register.html")
        if len(password) < 6:
            flash("Password must contain at least 6 characters.", "error")
            return render_template("register.html")
        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO users(name,email,password_hash,course,semester,roll_no) VALUES(?,?,?,?,?,?)",
                (name,email,generate_password_hash(password),course,semester,roll_no)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            flash("An account with this email already exists.", "error")
            return render_template("register.html")
        conn.close()
        flash("Account created successfully. Please login.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        from werkzeug.security import check_password_hash
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        conn.close()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            return redirect(url_for("dashboard"))
        flash("Invalid email or password.", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
    records = conn.execute("SELECT * FROM academic_records WHERE user_id=? ORDER BY id DESC", (session["user_id"],)).fetchall()
    predictions = conn.execute("SELECT * FROM predictions WHERE user_id=? ORDER BY id DESC", (session["user_id"],)).fetchall()
    conn.close()
    latest = records[0] if records else None
    latest_prediction = predictions[0] if predictions else None
    totals = {
        "total_study_hours": round(sum(float(r["total_study_hours"]) for r in records), 1),
        "total_assignments": sum(int(r["total_assignments"]) for r in records),
        "completed_assignments": sum(int(r["completed_assignments"]) for r in records),
        "pending_assignments": sum(int(r["pending_assignments"]) for r in records)
    }
    totals["completion_rate"] = round(totals["completed_assignments"]/totals["total_assignments"]*100,1) if totals["total_assignments"] else 0
    return render_template("student_dashboard.html", user=user, latest=latest, latest_prediction=latest_prediction, totals=totals)

@app.route("/academic", methods=["GET","POST"])
@login_required
def academic():
    if request.method == "POST":
        try:
            study_hours=float(request.form["study_hours_per_day"])
            study_days=int(request.form["study_days"])
            total_assignments=int(request.form["total_assignments"])
            completed=int(request.form["completed_assignments"])
            attendance=float(request.form["attendance"])
            marks=float(request.form["previous_marks"])
            sleep=float(request.form["sleep_hours"])
            if not 0<=study_hours<=24: raise ValueError("Study hours/day must be between 0 and 24.")
            if study_days<0: raise ValueError("Study days cannot be negative.")
            if total_assignments<0 or completed<0 or completed>total_assignments: raise ValueError("Check assignment totals and completed assignments.")
            if not 0<=attendance<=100: raise ValueError("Attendance must be between 0 and 100.")
            if not 0<=marks<=100: raise ValueError("Previous marks must be between 0 and 100.")
            if not 0<=sleep<=24: raise ValueError("Sleep hours/day must be between 0 and 24.")
            total_hours=round(study_hours*study_days,2)
            pending=total_assignments-completed
            prediction,confidence=predict_performance(study_hours,attendance,marks,completed,sleep)
            conn=get_db()
            cur=conn.execute("""INSERT INTO academic_records
                (user_id,study_hours_per_day,total_study_hours,total_assignments,completed_assignments,pending_assignments,attendance,previous_marks,sleep_hours)
                VALUES(?,?,?,?,?,?,?,?,?)""",
                (session["user_id"],study_hours,total_hours,total_assignments,completed,pending,attendance,marks,sleep))
            conn.execute("INSERT INTO predictions(user_id,academic_id,prediction,confidence) VALUES(?,?,?,?)",
                         (session["user_id"],cur.lastrowid,prediction,confidence))
            conn.commit(); conn.close()
            flash(f"Prediction: {prediction} ({confidence}% confidence). Total study hours: {total_hours}.","success")
            return redirect(url_for("dashboard"))
        except (ValueError,KeyError) as e:
            flash(str(e),"error")
    return render_template("academic.html")

@app.route("/history")
@login_required
def history():
    conn=get_db()
    rows=conn.execute("""SELECT a.*,p.prediction,p.confidence,p.created_at AS prediction_date
                         FROM academic_records a LEFT JOIN predictions p ON p.academic_id=a.id
                         WHERE a.user_id=? ORDER BY a.id DESC""",(session["user_id"],)).fetchall()
    conn.close()
    return render_template("history_student.html",rows=rows)

@app.route("/api/predict", methods=["POST"])
@login_required
def api_predict():
    data=request.get_json(silent=True) or request.form
    try:
        prediction,confidence=predict_performance(float(data["study_hours"]),float(data["attendance"]),
            float(data["previous_marks"]),int(data["completed_assignments"]),float(data["sleep_hours"]))
        return jsonify(success=True,prediction=prediction,confidence=confidence)
    except Exception as e:
        return jsonify(success=False,error=str(e)),400

@app.route("/api/health")
def health():
    return jsonify(status="ok",project="Student Performance Predictor")

if __name__=="__main__":
    init_db()
    app.run(debug=True)
