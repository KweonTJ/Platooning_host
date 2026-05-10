const historySize = 120;
const spacingHistory = [];

const $ = (id) => document.getElementById(id);

function getObject(value) {
  return value && typeof value === "object" ? value : {};
}

function fmt(value, digits = 2, suffix = "") {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "-";
  }
  return `${Number(value).toFixed(digits)}${suffix}`;
}

function text(id, value) {
  const el = $(id);
  if (!el) {
    return;
  }
  el.textContent = value === null || value === undefined || value === "" ? "-" : value;
}

function setPill(id, label, state) {
  const el = $(id);
  if (!el) {
    return;
  }
  el.textContent = label;
  el.className = `pill ${state}`;
}

function setHealth(id, label, ok, warnWhenMissing = true) {
  const el = $(id);
  if (!el) {
    return;
  }
  let state = "bad";
  if (ok === true) {
    state = "ok";
  } else if (ok === null && warnWhenMissing) {
    state = "warn";
  }
  el.textContent = label;
  el.className = `health-cell ${state}`;
}

function drawChart() {
  const canvas = $("spacingChart");
  if (!canvas) {
    return;
  }
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    return;
  }
  const width = canvas.width;
  const height = canvas.height;
  ctx.clearRect(0, 0, width, height);

  ctx.fillStyle = "#121820";
  ctx.fillRect(0, 0, width, height);

  const padding = 28;
  const zeroY = height / 2;
  const range = 0.18;

  ctx.strokeStyle = "#3b4655";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(padding, zeroY);
  ctx.lineTo(width - padding, zeroY);
  ctx.stroke();

  ctx.fillStyle = "#a6b0bf";
  ctx.font = "14px system-ui";
  ctx.fillText("+0.18m", 8, padding);
  ctx.fillText("0", 8, zeroY + 4);
  ctx.fillText("-0.18m", 8, height - padding);

  if (spacingHistory.length < 2) {
    ctx.fillStyle = "#a6b0bf";
    ctx.fillText("waiting for spacing data", padding, zeroY - 14);
    return;
  }

  const plotWidth = width - padding * 2;
  ctx.strokeStyle = "#4ea3ff";
  ctx.lineWidth = 3;
  ctx.beginPath();
  spacingHistory.forEach((sample, index) => {
    const x = padding + (plotWidth * index) / Math.max(historySize - 1, 1);
    const clipped = Math.max(-range, Math.min(range, sample));
    const y = zeroY - (clipped / range) * (height / 2 - padding);
    if (index === 0) {
      ctx.moveTo(x, y);
    } else {
      ctx.lineTo(x, y);
    }
  });
  ctx.stroke();

  const last = spacingHistory[spacingHistory.length - 1];
  ctx.fillStyle = Math.abs(last) <= 0.05 ? "#8ff0b4" : "#ffd983";
  ctx.beginPath();
  const lastX = padding + plotWidth * (spacingHistory.length - 1) / Math.max(historySize - 1, 1);
  const lastY = zeroY - (Math.max(-range, Math.min(range, last)) / range) * (height / 2 - padding);
  ctx.arc(lastX, lastY, 5, 0, Math.PI * 2);
  ctx.fill();
}

function update(data) {
  data = getObject(data);
  const server = getObject(data.server);
  const leader = getObject(data.leader);
  const follower = getObject(data.follower);
  const health = getObject(data.health);

  text("hostDomain", server.host_domain_id || server.ros_domain_id || "-");
  text("simulationDomain", server.simulation_domain_id);
  text("followerDomain", server.follower_domain_id);
  text("clock", server.time_label);

  const overall = health.overall || "WAIT";
  setPill("overall", overall, overall === "OK" ? "ok" : overall === "WARN" ? "warn" : "neutral");

  const linkOk = health.leader_link && health.follower_link;
  setPill("linkState", linkOk ? "Linked" : "Link Check", linkOk ? "ok" : "warn");

  text("leaderTask", leader.task_state);
  text("leaderCargo", `cargo ${leader.cargo_state || "-"}`);
  text("platoonMode", leader.platoon_mode);
  text("followerEnable", `enable ${leader.follower_enable === true ? "true" : "false"}`);
  text("followerStatus", follower.status);
  text("safetyState", `safety ${follower.safety_state || "-"}`);

  const spacingError = follower.distance_error_m;
  text("spacingError", fmt(spacingError, 3, " m"));
  text(
    "targetDistance",
    `target ${fmt(server.target_spacing_m, 2, " m")} · measured ${fmt(follower.target_distance_m, 2, " m")}`,
  );

  if (spacingError !== null && spacingError !== undefined) {
    spacingHistory.push(Number(spacingError));
    while (spacingHistory.length > historySize) {
      spacingHistory.shift();
    }
  }
  drawChart();

  setPill(
    "targetVisible",
    follower.target_visible === true ? "Target Visible" : "Target Lost",
    follower.target_visible === true ? "ok" : "warn",
  );
  setPill(
    "activeState",
    health.platoon_active ? "Following" : "Standby",
    health.platoon_active ? "ok" : "neutral",
  );

  const cmd = getObject(leader.cmd_vel);
  const odom = getObject(leader.odom);
  text("leaderLinear", fmt(cmd.linear_x, 2, " m/s"));
  text("leaderAngular", fmt(cmd.angular_z, 2, " rad/s"));
  text("leaderX", fmt(odom.x, 2, " m"));
  text("leaderYaw", fmt(odom.yaw, 2, " rad"));

  setHealth("leaderLink", "Leader", health.leader_link);
  setHealth("followerLink", "Follower", health.follower_link);
  setHealth("spacingState", "Spacing", health.spacing_good);
  setHealth("safetyOk", "Safety", health.safety_ok);
}

async function poll() {
  try {
    const response = await fetch("/api/status", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    update(await response.json());
  } catch (error) {
    setPill("overall", "WAIT", "warn");
    setPill("linkState", "Server Check", "warn");
  }
}

setInterval(poll, 500);
poll();
