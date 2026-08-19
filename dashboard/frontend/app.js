// Phase 5 HMI client: connects to the WebSocket state feed, which
// reflects real Modbus TCP polls of the PLC. Turbine rotation and
// penstock flow-dashes are animated continuously with
// requestAnimationFrame rather than CSS keyframe animations, because
// changing a running CSS animation's duration every tick (to match
// the latest RPM/flow) restarts it from frame 0 in most browsers,
// which looked like a blink/stutter instead of smooth motion.

const RESERVOIR_INNER_TOP = 41;
const RESERVOIR_INNER_HEIGHT = 218;

const GATE_BASELINE_Y = 222;
const GATE_MAX_HEIGHT = 36;
const GATE_MIN_HEIGHT = 4;

// Updated once per WebSocket tick, read continuously by the animation loop.
let currentRpm = 0;
let currentFlow = 0;

let turbineAngleDeg = 0;
let flowDashOffset = 0;
let lastFrameTime = null;

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function connect() {
  const protocol = location.protocol === "https:" ? "wss://" : "ws://";
  const ws = new WebSocket(protocol + location.host + "/ws/state");

  ws.onopen = () => setConnectionStatus("connected");
  ws.onclose = () => {
    setConnectionStatus("disconnected");
    setTimeout(connect, 2000);
  };
  ws.onerror = () => ws.close();

  ws.onmessage = (event) => {
    const state = JSON.parse(event.data);

    if (state.plc_connected === false) {
      showPlcOffline(state);
      currentRpm = 0;
      currentFlow = 0;
      return;
    }

    updateSchematicStaticParts(state);
    updateReadouts(state);
    updateAlarmBanner(state);

    // These two feed the continuous animation loop below.
    currentRpm = state.turbine_rpm;
    currentFlow = state.flow_m3s;
  };
}

function setConnectionStatus(status) {
  const dot = document.getElementById("conn-dot");
  const label = document.getElementById("conn-label");
  dot.className = "dot dot-" + status;
  label.textContent = status === "connected" ? "LIVE" : "RECONNECTING...";
}

function showPlcOffline(state) {
  const banner = document.getElementById("alarm-banner");
  const text = document.getElementById("alarm-text");
  banner.className = "alarm-banner alarm-plc-offline";
  text.textContent = "PLC UNREACHABLE - dashboard cannot read Modbus registers";

  setText("val-level", "--");
  setText("val-gate", "--");
  setText("val-flow", "--");
  setText("val-rpm", "--");
  setText("val-power", "--");
  setText("val-latency", "--");
}

// Things that change only once per tick (not continuously animated):
// water level, gate position, breaker color.
function updateSchematicStaticParts(state) {
  const waterRect = document.getElementById("reservoir-water");
  const fillFraction = state.reservoir_level_pct / 100;
  const height = RESERVOIR_INNER_HEIGHT * fillFraction;
  const y = RESERVOIR_INNER_TOP + (RESERVOIR_INNER_HEIGHT - height);
  waterRect.setAttribute("y", y.toFixed(1));
  waterRect.setAttribute("height", height.toFixed(1));

  const gateBar = document.getElementById("gate-bar");
  const gateFraction = state.gate_position_pct / 100;
  const gateHeight = GATE_MIN_HEIGHT + gateFraction * GATE_MAX_HEIGHT;
  gateBar.setAttribute("height", gateHeight.toFixed(1));
  gateBar.setAttribute("y", (GATE_BASELINE_Y - gateHeight).toFixed(1));

  const breaker = document.getElementById("breaker-dot");
  breaker.style.fill = alarmColorVar(state.alarm_state);

  const flowLine = document.getElementById("penstock-flow");
  flowLine.style.opacity = state.flow_m3s > 0.5 ? "0.9" : "0.15";
}

// Continuous animation loop: runs every browser frame (~60fps),
// independent of the once-per-second WebSocket updates, so motion
// stays smooth even though the underlying data only refreshes once a
// second.
function animationLoop(timestamp) {
  if (lastFrameTime === null) lastFrameTime = timestamp;
  const deltaSeconds = (timestamp - lastFrameTime) / 1000;
  lastFrameTime = timestamp;

  // Turbine rotation speed: mapped from RPM for visibility, NOT a
  // literal real-time conversion (documented in physics-model.md's
  // spirit of stating simplifications explicitly).
  const rotationsPerSecond = clamp(0.2 + (currentRpm / 1500) * 1.3, 0.1, 2.5);
  turbineAngleDeg = (turbineAngleDeg + rotationsPerSecond * 360 * deltaSeconds) % 360;

  const rotor = document.getElementById("turbine-rotor");
  if (rotor) {
    rotor.style.transform = "rotate(" + turbineAngleDeg.toFixed(1) + "deg)";
  }

  // Penstock flow dash movement: speed mapped from flow rate.
  const dashSpeedPxPerSec = clamp(currentFlow * 2.2, 5, 220);
  flowDashOffset -= dashSpeedPxPerSec * deltaSeconds;

  const flowLine = document.getElementById("penstock-flow");
  if (flowLine) {
    flowLine.style.strokeDashoffset = flowDashOffset.toFixed(1);
  }

  requestAnimationFrame(animationLoop);
}

function alarmColorVar(alarmState) {
  switch (alarmState) {
    case "WARNING": return "var(--accent-warning)";
    case "CRITICAL": return "var(--accent-critical)";
    default: return "var(--accent-normal)";
  }
}

function updateReadouts(state) {
  setText("val-level", state.reservoir_level_pct + "%");
  setText("val-gate", state.gate_position_pct + "%  (target " + state.gate_target_pct + "%)");
  setText("val-flow", state.flow_m3s + " m3/s");
  setText("val-rpm", state.turbine_rpm + " RPM");
  setText("val-power", state.generator_power_mw + " MW");
  setText("val-latency", state.poll_latency_ms + " ms");
}

function setText(id, text) {
  document.getElementById(id).textContent = text;
}

function updateAlarmBanner(state) {
  const banner = document.getElementById("alarm-banner");
  const text = document.getElementById("alarm-text");

  banner.className = "alarm-banner alarm-" + state.alarm_state.toLowerCase();

  const messages = {
    NORMAL: "NORMAL - plant operating within design limits",
    WARNING: "WARNING - turbine speed deviating from nominal",
    CRITICAL: "CRITICAL - abnormal plant state, investigate immediately"
  };
  text.textContent = messages[state.alarm_state] || state.alarm_state;
}

function setupGateControl() {
  const slider = document.getElementById("gate-slider");
  const sliderValue = document.getElementById("gate-slider-value");
  const button = document.getElementById("gate-set-btn");
  const status = document.getElementById("gate-set-status");

  slider.addEventListener("input", () => {
    sliderValue.textContent = slider.value + "%";
  });

  button.addEventListener("click", async () => {
    status.textContent = "Sending...";
    try {
      const response = await fetch("/api/gate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_pct: Number(slider.value) })
      });
      if (!response.ok) throw new Error("Request failed");
      status.textContent = "Sent via Modbus - watch the schematic respond.";
    } catch (err) {
      status.textContent = "Failed to send command.";
    }
    setTimeout(() => { status.textContent = ""; }, 4000);
  });
}

connect();
setupGateControl();
requestAnimationFrame(animationLoop);

startAlarmLogPolling();

// --- Alarm event log (polled separately, since transitions are rare
// compared to the once-per-second telemetry stream) ---
function startAlarmLogPolling() {
  refreshAlarmLog();
  setInterval(refreshAlarmLog, 5000);
}

async function refreshAlarmLog() {
  try {
    const response = await fetch("/api/alarms?limit=20");
    const events = await response.json();
    renderAlarmLog(events);
  } catch (err) {
    // Historian/backend unreachable - leave the table as-is rather
    // than clearing it, so a transient failure doesn't blank useful
    // history off the screen.
  }
}

function renderAlarmLog(events) {
  const body = document.getElementById("alarm-log-body");
  if (!events || events.length === 0) {
    body.innerHTML = '<tr><td colspan="3" class="log-empty">No alarm events yet.</td></tr>';
    return;
  }

  body.innerHTML = events.map(function (event) {
    const time = new Date(event.timestamp * 1000).toLocaleTimeString();
    const previous = event.previous_state === null ? "(startup)" : event.previous_state;
    const newStateClass = "log-state-" + event.new_state;
    return "<tr><td>" + time + "</td><td>" + previous + "</td>" +
           "<td class=\"" + newStateClass + "\">" + event.new_state + "</td></tr>";
  }).join("");
}