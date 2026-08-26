// Attack Path page: fetches the graph-state (was the attacker's most
// recent attempt able to reach the PLC?) and the structured attack
// timeline, both built from real logged experiment/historian data -
// no simulated or invented events.

async function loadGraphState() {
  try {
    const response = await fetch("/api/attack-graph-state");
    const state = await response.json();
    renderGraphState(state);
  } catch (err) {
    renderGraphState({ available: false, detail: "Could not reach backend." });
  }
}

function renderGraphState(state) {
  const edge = document.getElementById("edge-attack");
  const edgeLabel = document.getElementById("edge-attack-label");
  const banner = document.getElementById("graph-status-banner");
  const bannerText = document.getElementById("graph-status-text");

  if (!state.available) {
    edge.setAttribute("class", "edge-attack-unknown");
    edgeLabel.textContent = "no data";
    banner.className = "graph-status-banner graph-status-unknown";
    bannerText.textContent = state.detail || "No experiment has been run yet.";
    return;
  }

  if (state.path_reachable) {
    edge.setAttribute("class", "edge-attack-reachable");
    edgeLabel.textContent = "REACHABLE";
    banner.className = "graph-status-banner graph-status-reachable";
    bannerText.textContent =
      "ATTACK PATH REACHABLE (" + state.source_experiment + "): " + state.detail;
  } else {
    edge.setAttribute("class", "edge-attack-blocked");
    edgeLabel.textContent = "BLOCKED";
    banner.className = "graph-status-banner graph-status-blocked";
    bannerText.textContent =
      "ATTACK PATH BLOCKED (" + state.source_experiment + "): " + state.detail;
  }
}

async function loadTimeline() {
  const body = document.getElementById("timeline-body");
  try {
    const response = await fetch("/api/attack-timeline");
    const data = await response.json();

    if (!data.available || data.events.length === 0) {
      body.innerHTML =
        '<tr><td colspan="7" class="log-empty">' +
        (data.reason || "No timeline data available yet - run experiments/01-modbus-control/run_experiment.py") +
        "</td></tr>";
      return;
    }

    const t0 = data.events[0].timestamp;
    body.innerHTML = data.events.map(function (e) {
      const offset = (e.timestamp - t0).toFixed(2);
      const stageClass = "stage-badge stage-" + e.stage.replace(/[\/ ]/g, "-");
      return (
        "<tr>" +
        "<td>t+" + offset + "s</td>" +
        '<td><span class="' + stageClass + '">' + e.stage + "</span></td>" +
        "<td>" + e.source + "</td>" +
        "<td>" + e.target + "</td>" +
        "<td>" + e.protocol + "</td>" +
        "<td>" + e.action + "</td>" +
        "<td>" + e.result + "</td>" +
        "</tr>"
      );
    }).join("");
  } catch (err) {
    body.innerHTML = '<tr><td colspan="7" class="log-empty">Could not reach backend.</td></tr>';
  }
}

loadGraphState();
loadTimeline();