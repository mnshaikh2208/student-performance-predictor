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
);
