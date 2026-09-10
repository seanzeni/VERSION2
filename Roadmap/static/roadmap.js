(() => {
  const data = JSON.parse(document.getElementById("roadmap-data").textContent);
  const svg = document.querySelector("svg");
  const controls = document.getElementById("controls");
  const detail = document.querySelector(".detail");
  const mobile = document.querySelector(".mobile");
  const ns = "http://www.w3.org/2000/svg";
  const state = {};

  document.title = data.title;
  document.getElementById("heading").textContent = data.title;
  document.getElementById("subtitle").textContent = `${data.start_year}–${data.end_year} · ${data.subtitle}`;

  data.scenario_groups.forEach((group) => {
    state[group.id] = group.default;
    const field = document.createElement("div");
    field.className = "field";
    const label = document.createElement("label");
    label.htmlFor = `scenario-${group.id}`;
    label.textContent = group.label;
    const select = document.createElement("select");
    select.id = `scenario-${group.id}`;
    group.options.forEach((option) => {
      const item = document.createElement("option");
      item.value = option.value;
      item.textContent = option.label;
      item.selected = option.value === group.default;
      select.append(item);
    });
    select.addEventListener("change", () => { state[group.id] = select.value; draw(); });
    field.append(label, select);
    controls.append(field);
  });

  function node(name, attributes = {}, text = "") {
    const element = document.createElementNS(ns, name);
    Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, value));
    if (text) element.textContent = text;
    return element;
  }

  function visible(entry) {
    return !entry.when || Object.entries(entry.when).every(([key, value]) => state[key] === value);
  }

  function wrappedLines(label, width) {
    const limit = Math.max(4, Math.floor((width - 12) / 6.2));
    const lines = [""];
    for (const word of label.split(/\s+/)) {
      const candidate = `${lines.at(-1)} ${word}`.trim();
      if (candidate.length <= limit) lines[lines.length - 1] = candidate;
      else if (lines.length < 2) lines.push(word);
      else {
        const current = lines[1];
        lines[1] = (current.length + word.length + 1 <= limit ? `${current} ${word}` : current)
          .slice(0, Math.max(1, limit - 1)) + "…";
        break;
      }
    }
    return lines;
  }

  function drawDecision(entry, y, active, x) {
    const px = x(entry.point);
    const size = 7;
    const path = `M ${px} ${y} l ${size} ${size} l ${-size} ${size} l ${-size} ${-size} Z`;
    const show = () => { detail.textContent = `${entry.label} — ${entry.detail || ""}`; };
    svg.append(node("path", { d: path, class: "decision", opacity: active ? 1 : 0.14 }));
    if (active) {
      const text = node("text", { x: px + 12, y: y + 11, class: "bar-text decision-text" }, entry.label);
      text.addEventListener("click", show);
      svg.append(text);
    }
    const hit = node("rect", { x: px - 10, y: y - 8, width: Math.max(44, entry.label.length * 7 + 32), height: 36, class: "decision-hit", role: "button", tabindex: 0, "aria-label": `${entry.label}. ${entry.detail || ""}` });
    hit.addEventListener("click", show);
    hit.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") { event.preventDefault(); show(); }
    });
    svg.append(hit);
  }

  function drawBar(entry, index, y, active, x) {
    const start = x(entry.start);
    const end = x(Math.min(entry.end, data.end_year + 1));
    const width = Math.max(7, end - start - 3);
    const height = 23;
    const clipId = `bar-clip-${index}`;
    const defs = svg.querySelector("defs") || svg.insertBefore(node("defs"), svg.firstChild);
    const clip = node("clipPath", { id: clipId });
    clip.append(node("rect", { x: start + 3, y, width: Math.max(1, width - 6), height }));
    defs.append(clip);
    const bar = node("rect", { x: start, y, width, height, rx: 3, class: `bar ${entry.category || "program"}`, opacity: active ? 1 : 0.13, "aria-label": `${entry.label}. ${entry.detail || ""}` });
    bar.addEventListener("click", () => { detail.textContent = `${entry.label} — ${entry.detail || ""}`; });
    svg.append(bar);
    if (active && width > 34) {
      const text = node("text", { x: start + 6, y: y + 9, class: "bar-text", "clip-path": `url(#${clipId})` });
      wrappedLines(entry.label, width).forEach((line, lineIndex) => text.append(node("tspan", { x: start + 6, dy: lineIndex ? 11 : 0 }, line)));
      svg.append(text);
    }
  }

  function draw() {
    svg.replaceChildren();
    const width = 1200, left = 180, right = 12, top = 38, laneHeight = 106, bottom = 20;
    const height = top + data.lanes.length * laneHeight + bottom;
    const span = data.end_year - data.start_year + 1;
    const plotWidth = width - left - right;
    const x = (year) => left + ((year - data.start_year) / span) * plotWidth;
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    svg.append(node("title", { id: "svg-title" }, data.title));
    svg.append(node("desc", { id: "svg-desc" }, "Interactive swimlane roadmap. Use the scenario selectors to compare paths."));

    for (let year = data.start_year; year <= data.end_year; year += 1) {
      const px = x(year);
      svg.append(node("line", { x1: px, y1: top - 5, x2: px, y2: height - bottom, class: "year-line" }));
      svg.append(node("text", { x: px + 4, y: 20, class: "axis-text", "font-size": 13 }, String(year)));
    }
    svg.append(node("line", { x1: x(data.end_year + 1), y1: top - 5, x2: x(data.end_year + 1), y2: height - bottom, class: "year-line" }));

    data.lanes.forEach((lane, index) => {
      const y = top + index * laneHeight;
      if (lane.sub_lane) svg.append(node("rect", { x: 0, y, width, height: laneHeight, class: "sub-bg" }));
      svg.append(node("line", { x1: 0, y1: y + laneHeight, x2: width, y2: y + laneHeight, class: "lane-line" }));
      svg.append(node("text", { x: lane.sub_lane ? 20 : 5, y: y + 18, class: "lane-text", "font-size": 13, "font-weight": 600 }, lane.label));
    });

    data.entries.forEach((entry, index) => {
      const laneIndex = data.lanes.findIndex((lane) => lane.id === entry.lane);
      const y = top + laneIndex * laneHeight + 28 + (entry.row || 0) * 25;
      if (entry.point !== undefined) drawDecision(entry, y, visible(entry), x);
      else drawBar(entry, index, y, visible(entry), x);
    });

    mobile.innerHTML = data.entries.filter(visible).map((entry) => {
      const lane = data.lanes.find((item) => item.id === entry.lane);
      const timing = entry.point !== undefined ? `Decision: ${Math.floor(entry.point)}` : `${entry.start}–${Math.min(entry.end, data.end_year + 1)}`;
      return `<div><strong>${lane.label}: ${entry.label}</strong><span>${timing}</span></div>`;
    }).join("");
    detail.textContent = "Select a bar or decision point for its description. Faded items belong to another scenario.";
  }

  draw();
})();
