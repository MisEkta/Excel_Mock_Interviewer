const API_BASE = "http://localhost:8000/api/v1";
let sessionId = null;
let currentQuestion = null;

function show(section) {
  document.getElementById("welcome").style.display =
    section === "welcome" ? "block" : "none";
  document.getElementById("questionSection").style.display =
    section === "question" ? "block" : "none";
  document.getElementById("statusSection").style.display =
    section === "status" ? "block" : "none";
  document.getElementById("reportSection").style.display =
    section === "report" ? "block" : "none";
  document.getElementById("adminSection").style.display =
    section === "admin" ? "block" : "none";
  document.getElementById("loadingSection").style.display =
    section === "loadingSection" ? "block" : "none";
  document.getElementById("fullReportPage").style.display =
    section === "fullReportPage" ? "block" : "none";
}

async function startInterview() {
  const name = document.getElementById("candidateName").value.trim();
  if (!name) return alert("Please enter your name.");
  const res = await fetch(`${API_BASE}/interviews/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ candidate_name: name }),
  });
  const data = await res.json();
  sessionId = data.session_id;
  alert(data.message);
  getNextQuestion();
}

async function getNextQuestion() {
  const res = await fetch(`${API_BASE}/interviews/${sessionId}/next-question`);
  const data = await res.json();
  if (data.message) {
    show("status");
    document.getElementById("statusText").innerText = data.message;
    // Automatically fetch the report if interview is completed
    if (
      data.message.toLowerCase().includes("completed") ||
      data.message.toLowerCase().includes("no more questions")
    ) {
      getFinalReport();
    }
    return;
  }
  currentQuestion = data;
  show("question");
  document.getElementById(
    "questionText"
  ).innerHTML = `<strong>Q:</strong> ${data.question_text}`;
  document.getElementById("answerInput").value = "";
}

async function submitAnswer() {
  const answer = document.getElementById("answerInput").value.trim();
  if (!answer) return alert("Please enter your answer.");
  await fetch(`${API_BASE}/interviews/answer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      question_id: currentQuestion.question_id,
      response: answer,
    }),
  });
  getNextQuestion();
}

async function endInterview() {
  await fetch(`${API_BASE}/interviews/${sessionId}/end`, { method: "POST" });
  show("status");
  document.getElementById("statusText").innerText =
    "Thank you for attempting the interview!";
  document.getElementById("getReportBtn").style.display = "inline-block";
}

function renderReport(data) {
  let html = `
    <div class="report-card">
      <h3><span class="icon">&#x1F4C8;</span> Executive Summary</h3>
      <p>${data.executive_summary || "N/A"}</p>
      <h4><span class="icon">&#x1F4D6;</span> Proficiency Level: <span class="badge">${
        data.proficiency_level || "N/A"
      }</span></h4>
      <h4><span class="icon">&#x1F4AA;</span> Skill Scores</h4>
      <ul>
        ${
          data.skill_scores
            ? Object.entries(data.skill_scores)
                .map(
                  ([k, v]) =>
                    `<li><strong>${k.replace(/_/g, " ")}:</strong> ${v}</li>`
                )
                .join("")
            : ""
        }
      </ul>
      <h4><span class="icon">&#x1F4A1;</span> Strengths</h4>
      <ul>
        ${(data.strengths || []).map((s) => `<li>${s}</li>`).join("")}
      </ul>
      <h4><span class="icon">&#x1F4A9;</span> Weaknesses</h4>
      <ul>
        ${(data.weaknesses || []).map((w) => `<li>${w}</li>`).join("")}
      </ul>
      <h4><span class="icon">&#x1F4DD;</span> Recommendations</h4>
      <ul>
        ${(data.recommendations || []).map((r) => `<li>${r}</li>`).join("")}
      </ul>
      <h4><span class="icon">&#x1F4C4;</span> Detailed Analysis</h4>
      <p>${data.detailed_feedback || data.detailed_analysis || "N/A"}</p>
      <h4><span class="icon">&#x23F1;</span> Interview Duration</h4>
      <p>${
        data.interview_duration_minutes
          ? data.interview_duration_minutes + " min"
          : "N/A"
      }</p>
    </div>
  `;
  document.getElementById("fullReportText").innerHTML = html;
}

async function getFinalReport() {
  show("loadingSection");
  document.getElementById("loadingSection").style.display = "block";
  // Try fetching the report every 2 seconds until available
  let attempts = 0;
  let reportFetched = false;
  while (attempts < 10 && !reportFetched) {
    const res = await fetch(`${API_BASE}/interviews/${sessionId}/report`);
    if (res.status === 200) {
      const data = await res.json();
      show("fullReportPage");
      renderReport(data);
      reportFetched = true;
      break;
    }
    // Show loading for a bit longer
    await new Promise((resolve) => setTimeout(resolve, 2000));
    attempts++;
  }
  if (!reportFetched) {
    show("fullReportPage");
    document.getElementById("fullReportText").innerHTML =
      "<div class='error'>Sorry, your report could not be generated at this time. Please try again later.</div>";
  }
}

async function getStatus() {
  const res = await fetch(`${API_BASE}/interviews/${sessionId}/status`);
  const data = await res.json();
  show("status");
  document.getElementById("statusText").innerText = JSON.stringify(
    data,
    null,
    2
  );
}

async function getResponses() {
  const res = await fetch(`${API_BASE}/interviews/${sessionId}/responses`);
  const data = await res.json();
  show("report");
  document.getElementById("reportText").innerText = JSON.stringify(
    data,
    null,
    2
  );
  document.getElementById("adminSection").style.display = "block";
}

async function deleteInterview() {
  const res = await fetch(`${API_BASE}/interviews/${sessionId}`, {
    method: "DELETE",
  });
  const data = await res.json();
  alert(data.message);
  show("welcome");
}

async function healthCheck() {
  const res = await fetch(`${API_BASE}/health`);
  const data = await res.json();
  alert("API Health: " + JSON.stringify(data));
}

show("welcome");
