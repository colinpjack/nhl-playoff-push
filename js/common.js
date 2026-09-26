const $ = (id) => document.getElementById(id);

const TERMS = {
  PTS: "Points. A win is worth 2. An overtime or shootout loss is worth 1. The standings are sorted on this number.",
  "PTS%": "Points percentage: points divided by the maximum available (2 per game). This is how clubs are compared when they have not played the same number of games.",
  RW: "Regulation wins. The first tiebreaker after points. Overtime and shootout wins do not count.",
  ROW: "Regulation plus overtime wins. The second tiebreaker. Shootout wins are excluded.",
  Diff: "Goal differential: goals for minus goals against. A quick read on whether the points total is real.",
  xPTS: "Expected points from goal differential. The points total the scoring margin says the club should have.",
  L10: "Points and record over the last 10 games. A perfect 10-game run is 20 points.",
  "Last 3": "Record and goal differential over the last three games, or fewer if the club has not played three yet.",
  GR: "Games remaining. Each one is worth as many as 2 points.",
  Pace: "Current points rate stretched across the full regular-season schedule.",
  Path: "Top three in the division is an automatic berth. Otherwise the club is in the wild-card pool. Two wild cards get in.",
  WC: "Wild card: the two conference berths left after the three automatic qualifiers from each division.",
  Odds: "Share of simulated seasons in which this club finishes top three in its division or grabs a wild card. Not a betting line.",
  SOS: "Strength of the remaining schedule: the average points rate of the opponents still left.",
  Series: "Games left against the club this page is about.",
  SO: "Shootout wins. They are worth two points, but they do not count as regulation wins or as ROW.",
  GP: "Games played.",
  "W-L-OT": "Wins, regulation losses, and overtime or shootout losses.",
  PB: "Points back of the cut line: the last playoff spot in that conference. A plus means this club is ahead of that spot. A dash means they are even.",
  Power: "A blend of points percentage, shrunk toward a .500 club, and the goal margin over the last three games. A way to sort the league. Not an official NHL ranking.",
  Move: "Places moved in the power rankings since the order was frozen at the start of this week. A dash means no change.",
  Magic: "Points still to bank to clinch a berth no matter how the rest of the conference finishes. A win is 2. IN means the berth is already locked. OUT means it is gone.",
  STRK: "Current winning or losing streak. OT means the run is overtime or shootout losses.",
};

function assetRoot() {
  return (window.TEAM_PAGE && window.TEAM_PAGE.assetRoot) || "";
}

function teamHref(abbr) {
  if (!abbr) return assetRoot() || "./";
  return `${assetRoot()}teams/${String(abbr).toLowerCase()}/`;
}

function term(code, label = code) {
  const def = TERMS[code];
  if (!def) return esc(label);
  return `<abbr class="term" tabindex="0" title="${esc(def)}" data-tip="${esc(def)}">${esc(label)}</abbr>`;
}

function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function fmtDate(iso, withTime = false) {
  if (!iso) return "";
  if (!withTime && /^\d{4}-\d{2}-\d{2}$/.test(iso)) {
    const [year, month, day] = iso.split("-").map(Number);
    return new Intl.DateTimeFormat("en-US", {
      weekday: "short", month: "short", day: "numeric",
    }).format(new Date(year, month - 1, day));
  }
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  const opts = withTime
    ? { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZone: "America/New_York" }
    : { weekday: "short", month: "short", day: "numeric", timeZone: "America/New_York" };
  return new Intl.DateTimeFormat("en-US", opts).format(date);
}

function relativeTime(iso) {
  const date = new Date(iso);
  const mins = Math.max(0, Math.round((Date.now() - date.getTime()) / 60000));
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return fmtDate(iso, true);
}

function ptsPct(value) {
  if (value == null || value === "") return "—";
  const text = Number(value).toFixed(3);
  return text.startsWith("0") ? text.slice(1) : text;
}

function signed(value) {
  if (value == null || value === "") return "—";
  const text = String(value);
  if (text.startsWith("+") || text.startsWith("-") || text === "0") return text;
  const n = Number(value);
  if (Number.isNaN(n)) return text;
  return `${n > 0 ? "+" : ""}${n}`;
}

function fmtOdds(pct) {
  if (pct == null || Number.isNaN(Number(pct))) return "—";
  const n = Number(pct);
  if (n > 0 && n < 1) return "<1%";
  if (n < 10) return `${n.toFixed(1)}%`;
  return `${Math.round(n)}%`;
}

function trendBadge(direction) {
  if (!direction || direction === "flat") return "";
  const arrow = direction === "up" ? "▲" : "▼";
  return `<span class="trend ${esc(direction)}">${arrow}</span>`;
}

function teamCell(team) {
  return `<a class="team-cell" href="${teamHref(team.abbr)}">
    <img src="${esc(team.logo)}" alt="" />
    <span>${esc(team.abbr)}</span>
  </a>`;
}

function headerRow(labels) {
  return `<tr>${labels.map((label) => `<th>${label}</th>`).join("")}</tr>`;
}

function moveCell(move) {
  const n = Number(move) || 0;
  if (!n) return `<span class="move flat">—</span>`;
  if (n > 0) return `<span class="move up">▲ ${n}</span>`;
  return `<span class="move down">▼ ${Math.abs(n)}</span>`;
}

function bindTermTips() {
  let tip = document.getElementById("termTip");
  if (!tip) {
    tip = document.createElement("div");
    tip.id = "termTip";
    tip.className = "term-tip";
    tip.setAttribute("role", "tooltip");
    document.body.appendChild(tip);
  }
  document.querySelectorAll("abbr.term").forEach((el) => {
    if (!el.dataset.tip && el.getAttribute("title")) el.dataset.tip = el.getAttribute("title");
    if (el.dataset.tip && !el.getAttribute("aria-label")) {
      el.setAttribute("aria-label", `${el.textContent}: ${el.dataset.tip}`);
    }
    el.removeAttribute("title");
  });
  const place = (el) => {
    const text = el.dataset.tip;
    if (!text) return;
    tip.textContent = text;
    tip.classList.add("show");
    const pad = 12;
    const rect = el.getBoundingClientRect();
    const left = Math.max(pad, Math.min(rect.left + rect.width / 2 - tip.offsetWidth / 2, window.innerWidth - tip.offsetWidth - pad));
    let top = rect.top - tip.offsetHeight - 8;
    if (top < pad) top = Math.min(rect.bottom + 8, window.innerHeight - tip.offsetHeight - pad);
    tip.style.left = `${Math.round(left)}px`;
    tip.style.top = `${Math.round(top)}px`;
  };
  const hide = () => tip.classList.remove("show");
  if (bindTermTips.bound) return;
  bindTermTips.bound = true;
  document.addEventListener("pointerover", (event) => {
    const el = event.target.closest?.("abbr.term");
    if (el) place(el);
  });
  document.addEventListener("pointerout", (event) => {
    const el = event.target.closest?.("abbr.term");
    if (!el) return;
    if (event.relatedTarget && el.contains(event.relatedTarget)) return;
    hide();
  });
  document.addEventListener("focusin", (event) => {
    const el = event.target.closest?.("abbr.term");
    if (el) place(el);
  });
  document.addEventListener("focusout", hide);
  window.addEventListener("scroll", hide, true);
}
