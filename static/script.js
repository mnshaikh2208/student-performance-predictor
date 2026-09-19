const form = document.getElementById("form");
const error = document.getElementById("error");

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  error.textContent = "";

  const button = form.querySelector("button");
  button.disabled = true;
  button.textContent = "Predicting...";

  const payload = {
    student_name: document.getElementById("student_name").value,
    study_hours: document.getElementById("study_hours").value,
    attendance: document.getElementById("attendance").value,
    previous_marks: document.getElementById("previous_marks").value,
    assignments: document.getElementById("assignments").value,
    sleep_hours: document.getElementById("sleep_hours").value
  };

  try {
    const response = await fetch("/api/predict", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload)
    });

    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Prediction failed.");

    document.getElementById("waiting").classList.add("hidden");
    document.getElementById("answer").classList.remove("hidden");

    const p = document.getElementById("prediction");
    p.textContent = data.prediction;
    p.className = "big " + data.prediction.toLowerCase();

    document.getElementById("confidence").textContent =
      data.confidence !== null ? `Model confidence: ${data.confidence}%` : "";

  } catch (err) {
    error.textContent = err.message;
  } finally {
    button.disabled = false;
    button.textContent = "🔮 Predict My Performance";
  }
});
