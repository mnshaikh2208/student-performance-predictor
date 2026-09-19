import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

# Educational sample data.
# Replace this with a larger real dataset for a serious project.
data = {
    "study_hours": [1,2,3,4,5,6,7,8,2,3,6,7,1,4,5,8,9,2,4,6],
    "attendance": [50,55,60,65,70,75,80,90,52,62,78,85,45,68,74,92,95,58,72,88],
    "previous_marks": [35,40,45,50,55,60,65,80,38,48,68,75,30,52,58,88,92,42,60,78],
    "assignments": [2,3,4,5,6,7,8,10,2,4,8,9,1,5,6,10,10,3,6,9],
    "sleep_hours": [5,5,6,6,7,7,7,8,5,6,7,8,4,6,7,8,8,5,7,8],
    "result": [
        "Fail","Fail","Fail","Fail","Pass","Pass","Pass","Pass",
        "Fail","Fail","Pass","Pass","Fail","Fail","Pass","Pass",
        "Pass","Fail","Pass","Pass"
    ]
}

df = pd.DataFrame(data)

features = [
    "study_hours", "attendance", "previous_marks",
    "assignments", "sleep_hours"
]

X = df[features]
y = df["result"]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.25, random_state=42, stratify=y
)

model = DecisionTreeClassifier(max_depth=4, random_state=42)
model.fit(X_train, y_train)

y_pred = model.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)

joblib.dump(model, "model.pkl")

print("=" * 50)
print("Model trained successfully.")
print(f"Demo test accuracy: {accuracy * 100:.2f}%")
print("Saved: model.pkl")
print("=" * 50)

print("\nNote: this dataset has only 20 rows, split into a 15/5")
print("train/test set — these numbers are for demonstration only,")
print("not a statistically meaningful evaluation.\n")

print("Classification report (test set):")
print(classification_report(y_test, y_pred, zero_division=0))

print("Confusion matrix (rows=actual, cols=predicted, labels=[Fail, Pass]):")
print(confusion_matrix(y_test, y_pred, labels=["Fail", "Pass"]))

print("\nFeature importance (how much weight each input gets):")
for feat, importance in sorted(
    zip(features, model.feature_importances_),
    key=lambda x: x[1], reverse=True
):
    print(f"  {feat:<16} {importance:.3f}")
