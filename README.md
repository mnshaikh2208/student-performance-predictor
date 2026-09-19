# Student Performance Predictor

A Flask + SQLite + Machine Learning academic micro-project.

## Run on Windows / VS Code

1. Extract this ZIP.
2. Open the folder containing `app.py` in VS Code.
3. Open **Terminal → New Terminal**.
4. Verify that `app.py` and `requirements.txt` are shown by:
   `dir`
5. Install dependencies:
   `python -m pip install -r requirements.txt`
6. Start:
   `python app.py`
7. Open:
   `http://127.0.0.1:5000/`

## Student portal

Register → Login → Dashboard → Academic Data → Prediction → History.

Academic fields include:
- Study hours/day
- Number of study days
- Total study hours (calculated)
- Total assignments
- Completed assignments
- Pending assignments (calculated)
- Attendance
- Previous marks
- Sleep hours/day

## Admin / Teacher portal

Frontend button: **🔐 Admin Portal**

Direct URL:
`http://127.0.0.1:5000/admin/login`

Demo credentials:
- Email: `admin@studentpredictor.local`
- Password: `admin123`

Admin features:
- Registered students
- Prediction statistics
- Academic records
- Prediction + confidence
- Delete student
- Delete academic record
- CSV export

## Important ML note

The supplied `model.pkl` is retained from the original project. Its training dataset is small, so model quality should be treated as demonstration-level until the dataset is expanded and the model is properly evaluated.
