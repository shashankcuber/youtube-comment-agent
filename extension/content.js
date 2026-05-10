function renderExecutionSteps(steps) {
  if (!steps || steps.length === 0) {
    return "";
  }

  return `
    <div class="cp-card">
      <h4>Agent Execution Steps</h4>

      <div class="cp-step-list">
        ${steps.map(step => renderExecutionStep(step)).join("")}
      </div>
    </div>
  `;
}


function renderExecutionStep(step) {
  const icon = getStepIcon(step.status);
  const cssClass = getStepClass(step.status);

  const duration = step.duration_seconds !== null && step.duration_seconds !== undefined
    ? `<span class="cp-step-duration">${step.duration_seconds}s</span>`
    : "";

  const message = step.message
    ? `<div class="cp-step-message">${escapeHtml(step.message)}</div>`
    : "";

  return `
    <div class="cp-step ${cssClass}">
      <div class="cp-step-main">
        <span class="cp-step-icon">${icon}</span>
        <span class="cp-step-label">${escapeHtml(step.label || step.node)}</span>
        ${duration}
      </div>
      ${message}
    </div>
  `;
}


function getStepIcon(status) {
  switch (status) {
    case "success":
      return "✅";
    case "failed":
      return "❌";
    case "running":
      return "⏳";
    case "fallback":
      return "🔁";
    case "skipped":
      return "⏭️";
    default:
      return "•";
  }
}


function getStepClass(status) {
  switch (status) {
    case "success":
      return "cp-step-success";
    case "failed":
      return "cp-step-failed";
    case "running":
      return "cp-step-running";
    case "fallback":
      return "cp-step-fallback";
    case "skipped":
      return "cp-step-skipped";
    default:
      return "cp-step-default";
  }
}
function renderGenerationSource(result) {
  const status = result.llm_status;

  if (!status) {
    return "Unknown";
  }

  if (status.success) {
    return `Local LLM (${escapeHtml(status.model || "unknown model")})`;
  }

  if (status.attempted && !status.success) {
    return `Rule-based fallback. LLM failed: ${escapeHtml(status.model || "unknown model")}`;
  }

  return "Rule-based system";
}

function renderLLMStatus(result) {
  const status = result.llm_status;

  if (!status) {
    return "";
  }

  if (status.success) {
    return `
      <div class="cp-llm-success">
        <p><strong>LLM status:</strong> Success</p>
        <p><strong>Provider:</strong> ${escapeHtml(status.provider || "unknown")}</p>
        <p><strong>Model:</strong> ${escapeHtml(status.model || "unknown")}</p>
        <p><strong>Source:</strong> LLM raw comment analysis</p>
      </div>
    `;
  }

  if (status.attempted && !status.success) {
    return `
      <div class="cp-llm-failed">
        <p><strong>LLM status:</strong> Failed</p>
        <p><strong>Fallback:</strong> Rule-based analysis used</p>
        <p><strong>Provider:</strong> ${escapeHtml(status.provider || "unknown")}</p>
        <p><strong>Model:</strong> ${escapeHtml(status.model || "unknown")}</p>
        <p><strong>Error:</strong> ${escapeHtml(status.error || "Unknown error")}</p>
      </div>
    `;
  }

  return `
    <div class="cp-llm-disabled">
      <p><strong>LLM status:</strong> Not attempted</p>
      <p><strong>Output:</strong> Rule-based analysis used</p>
    </div>
  `;
}

function renderSentimentDistribution(distribution) {
  if (!distribution) {
    return "<p>No sentiment distribution available.</p>";
  }

  return `
    <ul>
      <li><strong>Positive:</strong> ${Math.round((distribution.positive || 0) * 100)}%</li>
      <li><strong>Negative:</strong> ${Math.round((distribution.negative || 0) * 100)}%</li>
      <li><strong>Neutral:</strong> ${Math.round((distribution.neutral || 0) * 100)}%</li>
      <li><strong>Warning:</strong> ${Math.round((distribution.warning || 0) * 100)}%</li>
    </ul>
  `;
}

function renderThemes(result) {
  return `
    <div class="cp-card">
      <h4>Public Themes</h4>

      <strong>Positive themes</strong>
      <ul>
        ${(result.positive_themes || []).map(theme => `<li>${escapeHtml(theme)}</li>`).join("")}
      </ul>

      <strong>Negative themes</strong>
      <ul>
        ${(result.negative_themes || []).map(theme => `<li>${escapeHtml(theme)}</li>`).join("")}
      </ul>

      <strong>Neutral themes</strong>
      <ul>
        ${(result.neutral_themes || []).map(theme => `<li>${escapeHtml(theme)}</li>`).join("")}
      </ul>

      <strong>Warning themes</strong>
      <ul>
        ${(result.warning_themes || []).map(theme => `<li>${escapeHtml(theme)}</li>`).join("")}
      </ul>
    </div>
  `;
}

function renderEvidenceComments(result) {
  const evidence = result.evidence_comments || [];

  if (evidence.length === 0) {
    return "";
  }

  return `
    <div class="cp-card">
      <h4>Evidence from Comments</h4>
      <ul>
        ${evidence.map(comment => `<li>${escapeHtml(comment)}</li>`).join("")}
      </ul>
    </div>
  `;
}

function getVideoIdFromUrl() {
  const url = new URL(window.location.href);
  return url.searchParams.get("v");
}

function createPanel() {
  if (document.getElementById("comment-pulse-panel")) {
    return;
  }

  const panel = document.createElement("div");
  panel.id = "comment-pulse-panel";

  panel.innerHTML = `
    <div class="cp-header">
      <strong>Comment Pulse</strong>
      <button id="cp-close">×</button>
    </div>

    <button id="cp-analyze-btn">Analyze Comments</button>

    <div id="cp-result">
      <p>Click analyze to understand what viewers think.</p>
    </div>
  `;

  document.body.appendChild(panel);

  document.getElementById("cp-close").addEventListener("click", () => {
    panel.remove();
  });

  document.getElementById("cp-analyze-btn").addEventListener("click", analyzeCurrentVideo);
}

async function analyzeCurrentVideo() {
  const videoId = getVideoIdFromUrl();
  const resultDiv = document.getElementById("cp-result");

  if (!videoId) {
    resultDiv.innerHTML = "<p>Could not find video ID.</p>";
    return;
  }

  resultDiv.innerHTML = "<p>Analyzing comments...</p>";

  try {
    const response = await fetch(
      `http://127.0.0.1:8000/analyze?video_id=${videoId}&max_comments=120&max_comments_for_llm=80`
    );
    if (!response.ok) {
      throw new Error("Backend request failed");
    }

    const data = await response.json();
    const result = data.result;
    
    resultDiv.innerHTML = `
    <div class="cp-card">
      <h3>Public Sentiment: ${formatLabel(result.overall_public_sentiment)}</h3>

      <p><strong>Watch rating:</strong> ${result.watch_rating}/10</p>
      <p><strong>Watch decision:</strong> ${escapeHtml(result.watch_decision)}</p>

      <p><strong>Generated by:</strong> ${renderGenerationSource(result)}</p>

      <p><strong>Public opinion:</strong> ${escapeHtml(result.public_opinion_summary)}</p>

      <p><strong>Recommendation:</strong> ${escapeHtml(result.recommendation)}</p>

      <p><strong>Raw comments fetched:</strong> ${result.total_raw_comments}</p>
      <p><strong>Comments sent to LLM:</strong> ${result.comments_sent_to_llm}</p>

    ${renderExecutionSteps(result.execution_steps)}
      ${renderLLMStatus(result)}
    </div>

    <div class="cp-card">
      <h4>Authenticity Signals</h4>
      <p><strong>Authenticity score:</strong> ${result.authenticity_score}/10</p>
      <p><strong>Authenticity label:</strong> ${formatLabel(result.authenticity_label)}</p>
      <p>${escapeHtml(result.authenticity_explanation)}</p>
    </div>

    <div class="cp-card">
      <h4>Sentiment Distribution</h4>
      ${renderSentimentDistribution(result.sentiment_distribution)}
    </div>

    ${renderThemes(result)}

    ${renderEvidenceComments(result)}
    `;

    // resultDiv.innerHTML = `
    //   <div class="cp-card">
    //     <h3>Overall: ${formatLabel(result.overall_sentiment)}</h3>
    //     <p><strong>Rating:</strong> ${result.watch_rating}/10</p>
    //     <p><strong>Recommendation:</strong> ${result.recommendation}</p>
    //     <p><strong>Summary:</strong> ${result.summary}</p>
    //     <p><strong>Comments analyzed:</strong> ${result.total_comments_analyzed}</p>
    //   </div>

    //   <div class="cp-card">
    //     <h4>Groups</h4>
    //     ${renderGroups(result.groups)}
    //   </div>
    // `;
  } catch (error) {
    resultDiv.innerHTML = `
      <p>Something went wrong.</p>
      <p>${error.message}</p>
    `;
  }
}

function renderGroups(groups) {
  return groups.map(group => {
    return `
      <div class="cp-group">
        <strong>${formatLabel(group.label)}:</strong> ${group.count}
        <ul>
          ${group.examples.map(example => `<li>${escapeHtml(example)}</li>`).join("")}
        </ul>
      </div>
    `;
  }).join("");
}

function formatLabel(label) {
  return label.replaceAll("_", " ");
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.innerText = text;
  return div.innerHTML;
}

function observeYouTubeNavigation() {
  let lastUrl = location.href;

  new MutationObserver(() => {
    const currentUrl = location.href;

    if (currentUrl !== lastUrl) {
      lastUrl = currentUrl;

      setTimeout(() => {
        if (window.location.href.includes("youtube.com/watch")) {
          createPanel();
        }
      }, 1000);
    }
  }).observe(document, { subtree: true, childList: true });
}

createPanel();
observeYouTubeNavigation();

