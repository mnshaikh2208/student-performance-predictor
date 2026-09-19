import os, sqlite3, csv, io
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, Response
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR=os.path.dirname(os.path.abspath(__file__))
DB_PATH=os.path.join(BASE_DIR,"student_performance.db")
MODEL_PATH=os.path.join(BASE_DIR,"model.pkl")

app=Flask(__name__)
app.secret_key=os.environ.get("SECRET_KEY","student-performance-project-secret-change-me")

ADMIN_EMAIL="admin@studentpredictor.local"
ADMIN_PASSWORD="admin123"

def db():
    c=sqlite3.connect(DB_PATH)
    c.row_factory=sqlite3.Row
    return c

def init_db():
    c=db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,email TEXT NOT NULL UNIQUE,password_hash TEXT NOT NULL,
      course TEXT DEFAULT '',semester TEXT DEFAULT '',roll_no TEXT DEFAULT '',
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS academic_records(
      id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,
      study_hours_per_day REAL NOT NULL,total_study_hours REAL NOT NULL,
      total_assignments INTEGER NOT NULL,completed_assignments INTEGER NOT NULL,
      pending_assignments INTEGER NOT NULL,attendance REAL NOT NULL,
      previous_marks REAL NOT NULL,sleep_hours REAL NOT NULL,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(user_id) REFERENCES users(id));
    CREATE TABLE IF NOT EXISTS predictions(
      id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,academic_id INTEGER,
      prediction TEXT NOT NULL,confidence REAL NOT NULL,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(user_id) REFERENCES users(id));
    """)
    c.commit(); c.close()

def student_required(fn):
    @wraps(fn)
    def w(*a,**k):
        if not session.get("user_id"): return redirect(url_for("login"))
        return fn(*a,**k)
    return w

def admin_required(fn):
    @wraps(fn)
    def w(*a,**k):
        if not session.get("admin"): return redirect(url_for("admin_login"))
        return fn(*a,**k)
    return w

@app.context_processor
def ctx():
    u=None
    if session.get("user_id"):
        c=db(); u=c.execute("SELECT id,name,email,course,semester,roll_no FROM users WHERE id=?",(session["user_id"],)).fetchone(); c.close()
    return {"current_user":u}

def ml_predict(study,attendance,marks,completed,sleep):
    try:
        import joblib
        if os.path.exists(MODEL_PATH):
            m=joblib.load(MODEL_PATH)
            x=[[study,attendance,marks,completed,sleep]]
            p=str(m.predict(x)[0])
            conf=float(max(m.predict_proba(x)[0])*100) if hasattr(m,"predict_proba") else 85.0
            return p,round(conf,1)
    except Exception:
        pass
    score=min(study/8,1)*20+(attendance/100)*25+(marks/100)*30+min(completed/10,1)*15+min(sleep/8,1)*10
    p="Pass" if score>=55 else "Fail"
    return p,round(max(50,min(99,score if p=="Pass" else 100-score)),1)

@app.route("/")
def index():
    return redirect(url_for("dashboard")) if session.get("user_id") else render_template("index.html")

@app.route("/about")
def about(): return render_template("about.html")

@app.route("/register",methods=["GET","POST"])
def register():
    if request.method=="POST":
        from werkzeug.security import generate_password_hash
        name=request.form.get("name","").strip(); email=request.form.get("email","").strip().lower()
        password=request.form.get("password",""); course=request.form.get("course","").strip()
        semester=request.form.get("semester","").strip(); roll=request.form.get("roll_no","").strip()
        if not name or not email or not password: flash("Name, email and password are required.","error"); return render_template("register.html")
        if len(password)<6: flash("Password must contain at least 6 characters.","error"); return render_template("register.html")
        c=db()
        try:
            c.execute("INSERT INTO users(name,email,password_hash,course,semester,roll_no) VALUES(?,?,?,?,?,?)",
                      (name,email,generate_password_hash(password),course,semester,roll)); c.commit()
        except sqlite3.IntegrityError:
            c.close(); flash("Email already registered.","error"); return render_template("register.html")
        c.close(); flash("Account created. Please login.","success"); return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        email=request.form.get("email","").strip().lower(); password=request.form.get("password","")
        c=db(); u=c.execute("SELECT * FROM users WHERE email=?",(email,)).fetchone(); c.close()
        if u and check_password_hash(u["password_hash"],password):
            session.clear(); session["user_id"]=u["id"]; return redirect(url_for("dashboard"))
        flash("Invalid email or password.","error")
    return render_template("login.html")

@app.route("/logout")
def logout(): session.clear(); return redirect(url_for("index"))

@app.route("/dashboard")
@student_required
def dashboard():
    c=db()
    u=c.execute("SELECT * FROM users WHERE id=?",(session["user_id"],)).fetchone()
    records=c.execute("SELECT * FROM academic_records WHERE user_id=? ORDER BY id DESC",(session["user_id"],)).fetchall()
    preds=c.execute("SELECT * FROM predictions WHERE user_id=? ORDER BY id DESC",(session["user_id"],)).fetchall()
    c.close()
    latest=records[0] if records else None; lp=preds[0] if preds else None
    total=sum(float(x["total_study_hours"]) for x in records)
    ta=sum(int(x["total_assignments"]) for x in records); ca=sum(int(x["completed_assignments"]) for x in records)
    totals={"study":round(total,1),"total_study_hours":round(total,1),"assignments":ta,"total_assignments":ta,"completed":ca,"completed_assignments":ca,"pending":sum(int(x["pending_assignments"]) for x in records),"pending_assignments":sum(int(x["pending_assignments"]) for x in records),
            "completion":round(ca/ta*100,1) if ta else 0,"completion_rate":round(ca/ta*100,1) if ta else 0}
    return render_template("student_dashboard.html",user=u,latest=latest,latest_prediction=lp,totals=totals)

@app.route("/academic",methods=["GET","POST"])
@student_required
def academic():
    if request.method=="POST":
        try:
            study=float(request.form["study_hours_per_day"]); days=int(request.form["study_days"])
            total=int(request.form["total_assignments"]); done=int(request.form["completed_assignments"])
            att=float(request.form["attendance"]); marks=float(request.form["previous_marks"]); sleep=float(request.form["sleep_hours"])
            if not 0<=study<=24 or days<0 or total<0 or done<0 or done>total or not 0<=att<=100 or not 0<=marks<=100 or not 0<=sleep<=24:
                raise ValueError("Please enter valid academic values.")
            total_hours=round(study*days,2); pending=total-done; pred,conf=ml_predict(study,att,marks,done,sleep)
            c=db(); cur=c.execute("""INSERT INTO academic_records
            (user_id,study_hours_per_day,total_study_hours,total_assignments,completed_assignments,pending_assignments,attendance,previous_marks,sleep_hours)
            VALUES(?,?,?,?,?,?,?,?,?)""",(session["user_id"],study,total_hours,total,done,pending,att,marks,sleep))
            c.execute("INSERT INTO predictions(user_id,academic_id,prediction,confidence) VALUES(?,?,?,?)",(session["user_id"],cur.lastrowid,pred,conf))
            c.commit(); c.close(); flash(f"Prediction: {pred} • Confidence: {conf}%","success"); return redirect(url_for("dashboard"))
        except Exception as e: flash(str(e),"error")
    return render_template("academic.html")

@app.route("/history")
@student_required
def history():
    c=db(); rows=c.execute("""SELECT a.*,p.prediction,p.confidence,p.created_at prediction_date
    FROM academic_records a LEFT JOIN predictions p ON p.academic_id=a.id
    WHERE a.user_id=? ORDER BY a.id DESC""",(session["user_id"],)).fetchall(); c.close()
    return render_template("history_student.html",rows=rows)

# ---------------- ADMIN ----------------
@app.route("/admin/login",methods=["GET","POST"])
def admin_login():
    if request.method=="POST":
        email=request.form.get("email","").strip().lower(); password=request.form.get("password","")
        if email==ADMIN_EMAIL and password==ADMIN_PASSWORD:
            session.clear(); session["admin"]=True; return redirect(url_for("admin_dashboard"))
        flash("Invalid admin credentials.","error")
    return render_template("admin_login_fixed.html")

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin",None); return redirect(url_for("admin_login"))

@app.route("/admin")
@admin_required
def admin_dashboard():
    c=db()
    students=c.execute("SELECT id,name,email,course,semester,roll_no,created_at FROM users ORDER BY id DESC").fetchall()
    records=c.execute("""SELECT a.*,u.name,u.email,u.roll_no,p.prediction,p.confidence
                         FROM academic_records a JOIN users u ON u.id=a.user_id
                         LEFT JOIN predictions p ON p.academic_id=a.id ORDER BY a.id DESC""").fetchall()
    stats=c.execute("""SELECT COUNT(*) n FROM users""").fetchone()["n"]
    predictions=c.execute("SELECT COUNT(*) n FROM predictions").fetchone()["n"]
    passes=c.execute("SELECT COUNT(*) n FROM predictions WHERE lower(prediction)='pass'").fetchone()["n"]
    fails=c.execute("SELECT COUNT(*) n FROM predictions WHERE lower(prediction)='fail'").fetchone()["n"]
    c.close()
    return render_template("admin_fixed.html",students=students,records=records,stats={"students":stats,"predictions":predictions,"passes":passes,"fails":fails})

@app.route("/admin/delete-record/<int:rid>",methods=["POST"])
@admin_required
def admin_delete_record(rid):
    c=db()
    c.execute("DELETE FROM predictions WHERE academic_id=?",(rid,))
    c.execute("DELETE FROM academic_records WHERE id=?",(rid,))
    c.commit(); c.close(); flash("Academic record deleted.","success"); return redirect(url_for("admin_dashboard"))

@app.route("/admin/delete-student/<int:uid>",methods=["POST"])
@admin_required
def admin_delete_student(uid):
    c=db()
    c.execute("DELETE FROM predictions WHERE user_id=?",(uid,))
    c.execute("DELETE FROM academic_records WHERE user_id=?",(uid,))
    c.execute("DELETE FROM users WHERE id=?",(uid,))
    c.commit(); c.close(); flash("Student and associated records deleted.","success"); return redirect(url_for("admin_dashboard"))

@app.route("/admin/export")
@admin_required
def admin_export():
    c=db()
    rows=c.execute("""SELECT u.name,u.email,u.roll_no,u.course,u.semester,
      a.study_hours_per_day,a.total_study_hours,a.total_assignments,a.completed_assignments,
      a.pending_assignments,a.attendance,a.previous_marks,a.sleep_hours,
      p.prediction,p.confidence,p.created_at
      FROM academic_records a JOIN users u ON u.id=a.user_id
      LEFT JOIN predictions p ON p.academic_id=a.id ORDER BY a.id DESC""").fetchall()
    c.close()
    out=io.StringIO(); w=csv.writer(out)
    w.writerow(["Name","Email","Roll No","Course","Semester","Study Hours/Day","Total Study Hours",
                "Total Assignments","Completed","Pending","Attendance %","Previous Marks %","Sleep Hours/Day","Prediction","Confidence %","Date"])
    for r in rows: w.writerow(list(r))
    return Response(out.getvalue(),mimetype="text/csv",headers={"Content-Disposition":"attachment; filename=student_performance_report.csv"})

@app.route("/api/health")
def health(): return jsonify(status="ok")

if __name__=="__main__":
    init_db()
    app.run(debug=True)
