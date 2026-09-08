// Security Monitoring page: polls three historian-backed endpoints
// and renders them as tables. All real data, no simulated rows.

function formatTime(unixSeconds) {
  return new Date(unixSeconds * 1000).toLocaleTimeString();
}

async function refreshIdsAlerts() {
  const body = document.getElementById("ids-alerts-body");
  try {
    const response = await fetch("/api/ids-alerts?limit=30");
    const alerts = await response.json();

    if (alerts.length === 0) {
      body.innerHTML = '<tr><td colspan="5" class="log-empty">No IDS alerts recorded yet.</td></tr>';
      return;
    }

    body.innerHTML = alerts.map(function (a) {
      const severityClass = "severity-" + a.severity;
      return (
        "<tr>" +
        "<td>" + formatTime(a.timestamp) + "</td>" +
        '<td class="' + severityClass + '">' + a.severity + "</td>" +
        "<td>" + a.rule + "</td>" +
        "<td>" + (a.source_ip || "-") + "</td>" +
        "<td>" + a.description + "</td>" +
        "</tr>"
      );
    }).join("");
  } catch (err) {
    body.innerHTML = '<tr><td colspan="5" class="log-empty">Could not reach backend.</td></tr>';
  }
}

async function refreshPlcEvents() {
  const body = document.getElementById("plc-events-body");
  try {
    const response = await fetch("/api/plc-events?limit=30");
    const events = await response.json();

    if (events.length === 0) {
      body.innerHTML = '<tr><td colspan="5" class="log-empty">No PLC events recorded yet.</td></tr>';
      return;
    }

    body.innerHTML = events.map(function (e) {
      return (
        "<tr>" +
        "<td>" + formatTime(e.timestamp) + "</td>" +
        "<td>" + e.register + "</td>" +
        "<td>" + (e.previous_raw === null ? "-" : e.previous_raw) + "</td>" +
        "<td>" + e.new_raw + "</td>" +
        "<td>" + (e.description || "-") + "</td>" +
        "</tr>"
      );
    }).join("");
  } catch (err) {
    body.innerHTML = '<tr><td colspan="5" class="log-empty">Could not reach backend.</td></tr>';
  }
}

async function refreshAlarmLog() {
  const body = document.getElementById("alarm-log-body");
  try {
    const response = await fetch("/api/alarms?limit=30");
    const events = await response.json();

    if (events.length === 0) {
      body.innerHTML = '<tr><td colspan="3" class="log-empty">No alarm events yet.</td></tr>';
      return;
    }

    body.innerHTML = events.map(function (e) {
      const previous = e.previous_state === null ? "(startup)" : e.previous_state;
      const newStateClass = "log-state-" + e.new_state;
      return (
        "<tr><td>" + formatTime(e.timestamp) + "</td><td>" + previous + "</td>" +
        '<td class="' + newStateClass + '">' + e.new_state + "</td></tr>"
      );
    }).join("");
  } catch (err) {
    body.innerHTML = '<tr><td colspan="3" class="log-empty">Could not reach backend.</td></tr>';
  }
}

function refreshAll() {
  refreshIdsAlerts();
  refreshPlcEvents();
  refreshAlarmLog();
}

refreshAll();
setInterval(refreshAll, 5000);