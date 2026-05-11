const $ = (id) => document.getElementById(id);
const history = {
  speed: [],
  spacing: [],
};
const maxHistory = 90;
const chartTheme = {
  backgroundStart: "rgba(255, 255, 255, 0.94)",
  backgroundEnd: "rgba(226, 235, 246, 0.72)",
  grid: "rgba(100, 116, 139, 0.22)",
  axisText: "rgba(30, 41, 59, 0.76)",
  reference: "rgba(2, 132, 199, 0.42)",
  leader: "#2563eb",
  follower: "#0891b2",
  spacing: "#f59e0b",
};

function getObject(value) {
  return value && typeof value === "object" ? value : {};
}

function getArray(value) {
  return Array.isArray(value) ? value : [];
}

function text(id, value) {
  const el = $(id);
  if (!el) {
    return;
  }
  el.textContent = value === null || value === undefined || value === "" ? "-" : value;
}

function fallback(value, defaultValue) {
  return value === null || value === undefined ? defaultValue : value;
}

function numberValue(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function pushHistory(key, values) {
  history[key].push({
    t: Date.now(),
    ...values,
  });
  if (history[key].length > maxHistory) {
    history[key] = history[key].slice(-maxHistory);
  }
}

function drawLineChart(id, series, options = {}) {
  const canvas = $(id);
  if (!canvas) {
    return;
  }
  const context = canvas.getContext("2d");
  const width = canvas.width;
  const height = canvas.height;
  const padding = { left: 28, right: 8, top: 10, bottom: 18 };
  context.clearRect(0, 0, width, height);
  const background = context.createLinearGradient(0, 0, width, height);
  background.addColorStop(0, chartTheme.backgroundStart);
  background.addColorStop(1, chartTheme.backgroundEnd);
  context.fillStyle = background;
  context.fillRect(0, 0, width, height);

  const allValues = [];
  series.forEach((line) => {
    line.points.forEach((point) => {
      if (numberValue(point.y) !== null) {
        allValues.push(point.y);
      }
    });
  });

  let min = numberValue(options.min);
  let max = numberValue(options.max);
  if (min === null) {
    min = allValues.length ? Math.min(...allValues) : -1;
  }
  if (max === null) {
    max = allValues.length ? Math.max(...allValues) : 1;
  }
  if (Math.abs(max - min) < 0.001) {
    max += 0.1;
    min -= 0.1;
  }
  const margin = (max - min) * 0.12;
  min -= margin;
  max += margin;

  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  const xFor = (index, count) => padding.left + (count <= 1 ? plotWidth : (plotWidth * index) / (count - 1));
  const yFor = (value) => padding.top + plotHeight - ((value - min) / (max - min)) * plotHeight;

  context.strokeStyle = chartTheme.grid;
  context.lineWidth = 1;
  for (let i = 0; i < 4; i += 1) {
    const y = padding.top + (plotHeight * i) / 3;
    context.beginPath();
    context.moveTo(padding.left, y);
    context.lineTo(width - padding.right, y);
    context.stroke();
  }

  if (numberValue(options.reference) !== null && options.reference >= min && options.reference <= max) {
    const y = yFor(options.reference);
    context.strokeStyle = chartTheme.reference;
    context.setLineDash([5, 5]);
    context.beginPath();
    context.moveTo(padding.left, y);
    context.lineTo(width - padding.right, y);
    context.stroke();
    context.setLineDash([]);
  }

  series.forEach((line) => {
    const points = line.points.filter((point) => numberValue(point.y) !== null);
    if (points.length === 0) {
      return;
    }
    context.strokeStyle = line.color;
    context.shadowColor = line.shadow || "rgba(2, 132, 199, 0.16)";
    context.shadowBlur = 5;
    context.lineWidth = 2;
    context.beginPath();
    points.forEach((point, index) => {
      const x = xFor(index, points.length);
      const y = yFor(point.y);
      if (index === 0) {
        context.moveTo(x, y);
      } else {
        context.lineTo(x, y);
      }
    });
    context.stroke();
    context.shadowBlur = 0;
  });

  context.fillStyle = chartTheme.axisText;
  context.font = "10px system-ui, sans-serif";
  context.fillText(max.toFixed(2), 3, padding.top + 4);
  context.fillText(min.toFixed(2), 3, height - padding.bottom);
}

function updateCharts(leaderMotion, followerMotion, follower) {
  const leaderSpeed = numberValue(getObject(leaderMotion).speed_mps);
  const followerSpeed = numberValue(getObject(followerMotion).speed_mps);
  const spacingError = numberValue(getObject(follower).distance_error_m);

  pushHistory("speed", {
    leader: leaderSpeed,
    follower: followerSpeed,
  });
  pushHistory("spacing", {
    error: spacingError,
  });

  text(
    "speedChartValue",
    `L ${leaderSpeed === null ? "-" : leaderSpeed.toFixed(2)} · F ${followerSpeed === null ? "-" : followerSpeed.toFixed(2)} m/s`,
  );
  text("spacingChartValue", spacingError === null ? "-" : `${spacingError.toFixed(3)} m`);

  drawLineChart("speedChart", [
    {
      color: chartTheme.leader,
      shadow: "rgba(37, 99, 235, 0.18)",
      points: history.speed.map((item) => ({ y: item.leader })),
    },
    {
      color: chartTheme.follower,
      shadow: "rgba(8, 145, 178, 0.18)",
      points: history.speed.map((item) => ({ y: item.follower })),
    },
  ], { min: 0 });

  drawLineChart("spacingChart", [
    {
      color: chartTheme.spacing,
      shadow: "rgba(245, 158, 11, 0.2)",
      points: history.spacing.map((item) => ({ y: item.error })),
    },
  ], {
    min: -0.2,
    max: 0.2,
    reference: 0,
  });

  const enoughData = history.speed.length > 4 || history.spacing.length > 4;
  setPill("graphState", enoughData ? "Live" : "Collecting", enoughData ? "ok" : "warn");
}

function formatSpeed(motion) {
  const speed = numberValue(getObject(motion).speed_mps);
  return speed === null ? "-" : `${speed.toFixed(2)} m/s`;
}

function formatAngular(motion) {
  const angular = numberValue(getObject(motion).angular_z_rad_s);
  return angular === null ? "angular -" : `angular ${angular.toFixed(2)} rad/s`;
}

function batteryKnown(battery) {
  battery = getObject(battery);
  return numberValue(battery.percentage) !== null || numberValue(battery.voltage) !== null;
}

function formatBattery(battery) {
  battery = getObject(battery);
  const percentage = numberValue(battery.percentage);
  if (percentage !== null) {
    return `${percentage.toFixed(0)}%`;
  }
  const voltage = numberValue(battery.voltage);
  return voltage === null ? "-" : `${voltage.toFixed(1)} V`;
}

function formatBatteryMeta(battery) {
  battery = getObject(battery);
  const voltage = numberValue(battery.voltage);
  const status = battery.status || "-";
  const voltageLabel = voltage === null ? "voltage -" : `voltage ${voltage.toFixed(1)} V`;
  return `${voltageLabel} · ${status}`;
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
  } else if (ok == null && warnWhenMissing) {
    state = "warn";
  }
  el.textContent = label;
  el.className = `health-cell ${state}`;
}

function videoLabel(stream) {
  stream = getObject(stream);
  const age = numberValue(stream.age_s);
  if (stream.available && age !== null) {
    return age < 1.5 ? "LIVE" : `${age.toFixed(1)}s`;
  }
  return "No Frame";
}

function videoStateClass(stream) {
  stream = getObject(stream);
  const age = numberValue(stream.age_s);
  if (!stream.available) {
    return "warn";
  }
  if (age !== null && age > 2.5) {
    return "warn";
  }
  return "ok";
}

function updateVideo(streams, key, ids) {
  const stream = getObject(streams[key]);
  setPill(ids.state, videoLabel(stream), videoStateClass(stream));
  text(ids.topic, stream.topic || "-");

  const overlay = $(ids.overlay);
  if (overlay) {
    const available = stream.available === true;
    const age = numberValue(stream.age_s);
    overlay.className = `video-overlay ${available && age !== null && age < 2.5 ? "hidden" : ""}`;
    if (stream.last_error) {
      overlay.textContent = stream.last_error;
    } else if (!available) {
      overlay.textContent = "waiting for image topic";
    } else {
      overlay.textContent = `last frame ${age === null ? "-" : age.toFixed(1)}s ago`;
    }
  }
}

function summarizeVideo(video) {
  const streams = [
    getObject(video.leader_debug),
    getObject(video.eef_debug),
    getObject(video.leader_raw),
    getObject(video.eef_raw),
  ];
  const live = streams.filter((stream) => {
    const age = numberValue(stream.age_s);
    return stream.available === true && age !== null && age < 2.5;
  }).length;
  const debugLive = [video.leader_debug, video.eef_debug].filter((stream) => {
    stream = getObject(stream);
    const age = numberValue(stream.age_s);
    return stream.available === true && age !== null && age < 2.5;
  }).length;
  const rawLive = [video.leader_raw, video.eef_raw].filter((stream) => {
    stream = getObject(stream);
    const age = numberValue(stream.age_s);
    return stream.available === true && age !== null && age < 2.5;
  }).length;

  return {
    label: live === 4 ? "OK" : live > 0 ? `${live}/4` : "No Frame",
    meta: `debug ${debugLive}/2 · raw ${rawLive}/2`,
  };
}

function summarizeSafety(follower, health) {
  follower = getObject(follower);
  const safetyState = follower.safety_state;
  const followerStatus = follower.status;
  const targetDistance = numberValue(follower.target_distance_m);
  const distanceError = numberValue(follower.distance_error_m);
  const meta = targetDistance === null
    ? `follower ${followerStatus || "-"}`
    : `dist ${targetDistance.toFixed(2)} m · err ${distanceError === null ? "-" : distanceError.toFixed(2)} m`;
  if (health.safety_ok === false) {
    return {
      label: safetyState || "STOP",
      meta,
    };
  }
  if (health.safety_ok === true) {
    return {
      label: safetyState || "OK",
      meta,
    };
  }
  return {
    label: safetyState || "-",
    meta,
  };
}

function eventLabel(event) {
  const value = String(event || "-").toLowerCase();
  if (value.includes("assigned")) {
    return "할당";
  }
  if (value.includes("picked") || value.includes("grasped")) {
    return "파지";
  }
  if (value.includes("placed") || value.includes("loaded")) {
    return "적재";
  }
  if (value.includes("cancel")) {
    return "취소";
  }
  return event || "-";
}

function stateClass(state) {
  const value = String(state || "").toLowerCase();
  if (value === "picked" || value === "placed") {
    return "ok";
  }
  if (value === "assigned") {
    return "warn";
  }
  if (value === "cancelled") {
    return "bad";
  }
  return "neutral";
}

function renderCargoList(cargo) {
  const list = $("cargoList");
  if (!list) {
    return;
  }
  const items = getArray(cargo.items);
  list.replaceChildren();

  if (items.length === 0) {
    const empty = document.createElement("li");
    empty.className = "empty-list";
    empty.textContent = "아직 파지 기록이 없습니다.";
    list.appendChild(empty);
    return;
  }

  items.forEach((item) => {
    const row = document.createElement("li");
    row.className = "cargo-item";

    const main = document.createElement("div");
    const id = document.createElement("strong");
    id.textContent = item.cargo_id || "-";
    const meta = document.createElement("small");
    meta.textContent = `${eventLabel(item.latest_event)} · ${item.updated_at || "-"}`;
    main.append(id, meta);

    const badge = document.createElement("span");
    badge.className = `cargo-badge ${stateClass(item.state)}`;
    badge.textContent = eventLabel(item.state);

    row.append(main, badge);
    list.appendChild(row);
  });
}

function update(data) {
  data = getObject(data);
  const server = getObject(data.server);
  const leader = getObject(data.leader);
  const follower = getObject(data.follower);
  const health = getObject(data.health);
  const task = getObject(data.task);
  const cargo = getObject(data.cargo);
  const video = getObject(data.video);
  const lastEvent = getObject(cargo.last_event);
  const leaderMotion = getObject(leader.motion);
  const followerMotion = getObject(follower.motion);
  const leaderBattery = getObject(leader.battery);
  const followerBattery = getObject(follower.battery);

  text("hostDomain", server.host_domain_id || server.ros_domain_id || "-");
  text("simulationDomain", server.simulation_domain_id);
  text("followerDomain", server.follower_domain_id);
  text("clock", server.time_label);

  const overall = health.overall || "WAIT";
  setPill("overall", overall, overall === "OK" ? "ok" : overall === "WARN" ? "warn" : "neutral");

  const linkOk = health.leader_link && health.follower_link;
  setPill("linkState", linkOk ? "Linked" : "Link Check", linkOk ? "ok" : "warn");

  text("approachState", task.approach_label);
  text("taskStage", `stage ${task.stage || "-"}`);
  text("graspState", task.grasp_label);
  text("leaderCargo", `cargo ${leader.cargo_state || "-"}`);
  text("pickedCount", fallback(cargo.picked_count, 0));
  text("placedCount", `placed ${fallback(cargo.placed_count, 0)}`);
  text("currentCargo", cargo.current_id);
  text("lastCargoEvent", `event ${eventLabel(lastEvent.event)}`);
  const videoSummary = summarizeVideo(video);
  text("videoSummary", videoSummary.label);
  text("videoSummaryMeta", videoSummary.meta);
  const safetySummary = summarizeSafety(follower, health);
  text("safetySummary", safetySummary.label);
  text("safetySummaryMeta", safetySummary.meta);

  text("leaderSpeed", formatSpeed(leaderMotion));
  text("leaderAngular", `${formatAngular(leaderMotion)} · ${leaderMotion.source || "-"}`);
  text("followerSpeed", formatSpeed(followerMotion));
  text("followerAngular", `${formatAngular(followerMotion)} · ${followerMotion.source || "-"}`);
  text("leaderBattery", formatBattery(leaderBattery));
  text("leaderBatteryMeta", formatBatteryMeta(leaderBattery));
  text("followerBattery", formatBattery(followerBattery));
  text("followerBatteryMeta", formatBatteryMeta(followerBattery));
  updateCharts(leaderMotion, followerMotion, follower);

  const leaderBatteryKnown = batteryKnown(leaderBattery);
  const followerBatteryKnown = batteryKnown(followerBattery);
  let batteryLabel = "Battery Check";
  let batteryClass = "warn";
  if (health.battery_ok === false) {
    batteryLabel = "Battery Low";
    batteryClass = "bad";
  } else if (leaderBatteryKnown && followerBatteryKnown) {
    batteryLabel = "Battery OK";
    batteryClass = "ok";
  } else if (leaderBatteryKnown || followerBatteryKnown) {
    batteryLabel = "Battery Partial";
    batteryClass = "warn";
  }
  setPill("batteryState", batteryLabel, batteryClass);

  text("leaderTask", leader.task_state);
  text("platoonMode", leader.platoon_mode);
  text("followerEnable", `enable ${leader.follower_enable === true ? "true" : "false"}`);
  text("controlStatus", task.mp_control_status || task.raw_status);
  text("simStatus", task.sim_pick_place_status);
  updateVideo(video, "leader_debug", {
    state: "leaderDebugVideoState",
    topic: "leaderDebugTopic",
    overlay: "leaderDebugOverlay",
  });
  updateVideo(video, "eef_debug", {
    state: "eefDebugVideoState",
    topic: "eefDebugTopic",
    overlay: "eefDebugOverlay",
  });
  updateVideo(video, "leader_raw", {
    state: "leaderRawVideoState",
    topic: "leaderRawTopic",
    overlay: "leaderRawOverlay",
  });
  updateVideo(video, "eef_raw", {
    state: "eefRawVideoState",
    topic: "eefRawTopic",
    overlay: "eefRawOverlay",
  });

  setPill(
    "activeState",
    task.approach_active ? "접근 중" : "대기",
    task.approach_active ? "ok" : "neutral",
  );
  setPill(
    "cargoListState",
    `${getArray(cargo.items).length} items`,
    getArray(cargo.items).length > 0 ? "ok" : "neutral",
  );

  renderCargoList(cargo);

  setHealth("leaderLink", "Leader", health.leader_link);
  setHealth("followerLink", "Follower", health.follower_link);
  setHealth("graspHealth", "Grasp", task.grasp_ok);
  setHealth("batteryHealth", "Battery", health.battery_ok);
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
