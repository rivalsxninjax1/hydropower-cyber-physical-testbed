// Experiments page: shows raw per-run data for both experiments plus
// the aggregated evaluation summary. All real data read from
// data/experiments/ via backend endpoints added in Phase 17.

function formatTime(unixSeconds) {
  return new Date(unixSeconds * 1000).toLocaleTimeString();
}

async function refreshExperiment01() {
  const body = document.getElementById("exp01-body");
  try {
    const response = await fetch("/api/experiments/01-modbus-control/runs?limit=20");
    const data = await response.json();

    if (!data.available || data.runs.length === 0) {
      body.innerHTML = '<tr><td colspan="7" class="log-empty">' +
        (data.reason || "No runs yet - see experiments/01-modbus-control/README.md") +
        "</td></tr>";
      return;
    }

    body.innerHTML = data.runs.map(function (r) {
      return (
        "<tr>" +
        "<td>" + formatTime(Number(r.timestamp)) + "</td>" +
        "<td>" + r.register_written + "</td>" +
        "<td>" + r.raw_value_written + "</td>" +
        "<td>" + r.write_accepted + "</td>" +
        "<td>" + r.alarm_state_changed + "</td>" +
        "<td>" + (r.time_to_alarm_change_s || "-") + "</td>" +
        "<td>" + r.attack_success + "</td>" +
        "</tr>"
      );
    }).join("");
  } catch (err) {
    body.innerHTML = '<tr><td colspan="7" class="log-empty">Could not reach backend.</td></tr>';
  }
}

async function refreshExperiment02() {
  const body = document.getElementById("exp02-body");
  try {
    const response = await fetch("/api/experiments/02-network-segmentation/runs?limit=20");
    const data = await response.json();

    if (!data.available || data.runs.length === 0) {
      body.innerHTML = '<tr><td colspan="5" class="log-empty">' +
        (data.reason || "No runs yet - see experiments/02-network-segmentation/README.md") +
        "</td></tr>";
      return;
    }

    body.innerHTML = data.runs.map(function (r) {
      return (
        "<tr>" +
        "<td>" + formatTime(Number(r.timestamp)) + "</td>" +
        "<td>" + r.target_host + "</td>" +
        "<td>" + r.dns_resolution_success + "</td>" +
        "<td>" + r.tcp_connect_success + "</td>" +
        "<td>" + r.attack_path_reachable + "</td>" +
        "</tr>"
      );
    }).join("");
  } catch (err) {
    body.innerHTML = '<tr><td colspan="5" class="log-empty">Could not reach backend.</td></tr>';
  }
}

async function refreshSummary() {
  const container = document.getElementById("summary-content");
  try {
    const response = await fetch("/api/experiments/summary");
    const data = await response.json();

    if (!data.available) {
      container.innerHTML = '<p class="log-empty">' + data.reason + "</p>";
      return;
    }

    let html = "";
    for (const experimentId in data.summary) {
      const exp = data.summary[experimentId];
      html += "<h3 style='font-size:13px;color:var(--text-primary);margin:16px 0 8px;'>" +
        experimentId + " (" + exp.run_count + " runs)</h3>";
      html += '<table class="log-table"><thead><tr><th>Column</th><th>Stats</th></tr></thead><tbody>';
      for (const columnName in exp.columns) {
        const stats = exp.columns[columnName];
        let statsText = "";
        if (stats.type === "boolean") {
          statsText = "True: " + stats.true_count + ", False: " + stats.false_count +
            " (rate: " + stats.true_rate + ")";
        } else if (stats.type === "numeric") {
          statsText = "mean=" + stats.mean + ", min=" + stats.min + ", max=" + stats.max +
            ", n=" + stats.count;
        }
        html += "<tr><td>" + columnName + "</td><td>" + statsText + "</td></tr>";
      }
      html += "</tbody></table>";
    }
    container.innerHTML = html;
  } catch (err) {
    container.innerHTML = '<p class="log-empty">Could not reach backend.</p>';
  }
}

refreshExperiment01();
refreshExperiment02();
refreshSummary();