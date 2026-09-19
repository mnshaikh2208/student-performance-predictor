async function loadDashboard() {
  let data;
  try {
    const res = await fetch("/api/stats");
    data = await res.json();
  } catch (err) {
    document.getElementById("emptyState").classList.remove("hidden");
    document.getElementById("emptyState").querySelector("h2").textContent =
      "Could not load stats";
    return;
  }

  if (!data.total) {
    document.getElementById("emptyState").classList.remove("hidden");
    return;
  }
  document.getElementById("dashboardContent").classList.remove("hidden");

  document.getElementById("statCards").innerHTML = `
    <div class="stat-card">
      <div class="stat-num">${data.total}</div>
      <div class="stat-label">Total Predictions</div>
    </div>
    <div class="stat-card pass">
      <div class="stat-num">${data.pass_count}</div>
      <div class="stat-label">Pass</div>
    </div>
    <div class="stat-card fail">
      <div class="stat-num">${data.fail_count}</div>
      <div class="stat-label">Fail</div>
    </div>
    <div class="stat-card">
      <div class="stat-num">${Math.round((data.pass_count / data.total) * 100)}%</div>
      <div class="stat-label">Pass Rate</div>
    </div>
  `;

  new Chart(document.getElementById("passFailChart"), {
    type: "doughnut",
    data: {
      labels: ["Pass", "Fail"],
      datasets: [{
        data: [data.pass_count, data.fail_count],
        backgroundColor: ["#16845b", "#c43d4f"]
      }]
    },
    options: { plugins: { legend: { position: "bottom" } } }
  });

  const featureLabels = Object.keys(data.feature_importance);
  if (featureLabels.length) {
    new Chart(document.getElementById("importanceChart"), {
      type: "bar",
      data: {
        labels: featureLabels,
        datasets: [{
          label: "Importance",
          data: featureLabels.map(f => data.feature_importance[f]),
          backgroundColor: "#5b5bd6"
        }]
      },
      options: { plugins: { legend: { display: false } }, indexAxis: "y" }
    });
  }

  const dates = Object.keys(data.trend);
  new Chart(document.getElementById("trendChart"), {
    type: "line",
    data: {
      labels: dates,
      datasets: [
        {
          label: "Pass",
          data: dates.map(d => data.trend[d].Pass),
          borderColor: "#16845b",
          backgroundColor: "#16845b33",
          tension: 0.25
        },
        {
          label: "Fail",
          data: dates.map(d => data.trend[d].Fail),
          borderColor: "#c43d4f",
          backgroundColor: "#c43d4f33",
          tension: 0.25
        }
      ]
    }
  });

  const avgLabels = Object.keys(data.averages);
  new Chart(document.getElementById("avgChart"), {
    type: "bar",
    data: {
      labels: avgLabels,
      datasets: [{
        label: "Average value",
        data: avgLabels.map(f => data.averages[f]),
        backgroundColor: "#5b5bd6"
      }]
    },
    options: { plugins: { legend: { display: false } } }
  });
}

loadDashboard();
