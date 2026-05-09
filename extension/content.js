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
      `http://127.0.0.1:8000/analyze?video_id=${videoId}&max_comments=100`
    );

    if (!response.ok) {
      throw new Error("Backend request failed");
    }

    const data = await response.json();
    const result = data.result;

    resultDiv.innerHTML = `
      <div class="cp-card">
        <h3>Overall: ${formatLabel(result.overall_sentiment)}</h3>
        <p><strong>Rating:</strong> ${result.watch_rating}/10</p>
        <p><strong>Recommendation:</strong> ${result.recommendation}</p>
        <p><strong>Summary:</strong> ${result.summary}</p>
        <p><strong>Comments analyzed:</strong> ${result.total_comments_analyzed}</p>
      </div>

      <div class="cp-card">
        <h4>Groups</h4>
        ${renderGroups(result.groups)}
      </div>
    `;
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