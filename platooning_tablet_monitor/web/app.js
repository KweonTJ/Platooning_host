const $ = (id) => document.getElementById(id);

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

function numberValue(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
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
  text("pickedCount", cargo.picked_count ?? 0);
  text("placedCount", `placed ${cargo.placed_count ?? 0}`);
  text("currentCargo", cargo.current_id);
  text("lastCargoEvent", `event ${eventLabel(lastEvent.event)}`);

  text("leaderSpeed", formatSpeed(leaderMotion));
  text("leaderAngular", `${formatAngular(leaderMotion)} · ${leaderMotion.source || "-"}`);
  text("followerSpeed", formatSpeed(followerMotion));
  text("followerAngular", `${formatAngular(followerMotion)} · ${followerMotion.source || "-"}`);
  text("leaderBattery", formatBattery(leaderBattery));
  text("leaderBatteryMeta", formatBatteryMeta(leaderBattery));
  text("followerBattery", formatBattery(followerBattery));
  text("followerBatteryMeta", formatBatteryMeta(followerBattery));

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
