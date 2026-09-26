function renderTicker(data) {
  const line = (data.ticker || []).join("   •   ") + "   •   ";
  $("tickerTrack").textContent = line + line;
}

function renderHero(data) {
  const narrative = data.narrative || {};
  const spot = data.spotlight || {};
  $("statusKicker").textContent = narrative.kicker || "";
  $("headline").textContent = narrative.headline || "";
  $("blurb").textContent = narrative.blurb || "";
  $("heroChips").innerHTML = (data.chips || [])
    .map((chip) => `<div class="chip"><span>${esc(chip.label)}</span><strong>${esc(chip.value)}</strong></div>`)
    .join("");
  const card = (label, club, className) => {
    if (!club) return "";
    const odds = club.playoffPct == null ? "" : ` · ${fmtOdds(club.playoffPct)}`;
    const line = club.points == null ? (club.record || "") : `${club.points} pts`;
    return `<a class="hero-score ${className || ""}" href="${teamHref(club.abbr)}">
      <p class="score-label">${esc(label)}</p>
      <p class="score-giant">${esc(club.abbr)}</p>
      <p class="score-sub">${esc(club.nickname || club.name || "")} · ${esc(line)}${esc(odds)}</p>
    </a>`;
  };
  $("heroMeters").innerHTML = [
    card("Power No. 1", spot.top, ""),
    card("East cut line", spot.east, "odds"),
    card("West cut line", spot.west, "magic"),
  ].join("");
  $("updatePill").textContent = `Updated ${relativeTime(data.generatedAt)}`;
  $("seasonPill").textContent = data.weekLabel || data.season || "NHL";
}

function renderClubs(data) {
  $("clubStrip").innerHTML = (data.clubs || []).map((team) => `
    <a class="club-link" href="${teamHref(team.abbr)}">
      <img src="${esc(team.logo)}" alt="" />
      <span>${esc(team.abbr)}</span>
    </a>
  `).join("");
}

function renderRankings(data) {
  $("rankingsBlurb").textContent = data.rankingsBlurb || "";
  const head = [
    "#", term("Move", "Move"), "Team", term("W-L-OT", "W-L-OT"), term("PTS"),
    term("Diff", "Diff"), term("Last 3", "Last 3"), term("STRK", "Strk"),
    term("Power", "Power"), term("Odds", "Odds"),
  ];
  document.querySelector("#rankTable thead").innerHTML = headerRow(head);
  document.querySelector("#rankTable tbody").innerHTML = (data.powerRankings || []).map((team) => `
    <tr>
      <td>${esc(team.rank)}</td>
      <td>${moveCell(team.move)}</td>
      <td>${teamCell(team)}</td>
      <td>${esc(team.record)}</td>
      <td>${esc(team.points)}</td>
      <td>${esc(signed(team.diff))}</td>
      <td>${esc(team.formRecord || "—")} · ${esc(signed(team.formDiff))}</td>
      <td>${esc(team.streak || "—")}</td>
      <td>${esc(team.power ?? "—")}</td>
      <td>${esc(fmtOdds(team.playoffPct))}</td>
    </tr>
  `).join("");
}

function standingsTable(tableId, rows) {
  const head = [
    "#", "Team", term("Path", "Path"), term("W-L-OT", "W-L-OT"), term("PTS"),
    term("PTS%"), term("RW"), term("Diff", "Diff"), term("PB", "PB"), term("Odds", "Odds"),
  ];
  const table = document.querySelector(tableId);
  table.querySelector("thead").innerHTML = headerRow(head);
  table.querySelector("tbody").innerHTML = (rows || []).map((team) => {
    const classes = [
      team.inField ? "row-in" : "",
      team.isCut ? "row-cut" : "",
    ].filter(Boolean).join(" ");
    const cut = team.isCut ? `<div class="cut-note">Last berth</div>` : "";
    return `<tr class="${classes}">
      <td>${esc(team.seed)}${cut}</td>
      <td>${teamCell(team)}</td>
      <td>${esc(team.path)}</td>
      <td>${esc(team.record)}</td>
      <td>${esc(team.points)}</td>
      <td>${esc(ptsPct(team.pointPct))}</td>
      <td>${esc(team.rw)}</td>
      <td>${esc(signed(team.diff))}</td>
      <td>${esc(team.pb ?? "—")}</td>
      <td>${esc(fmtOdds(team.playoffPct))}</td>
    </tr>`;
  }).join("");
}

function renderPicture(data) {
  $("eastBlurb").textContent = data.eastBlurb || "";
  $("westBlurb").textContent = data.westBlurb || "";
  standingsTable("#eastTable", data.east);
  standingsTable("#westTable", data.west);
}

function renderLeaders(data) {
  $("divLeaders").innerHTML = (data.leaders || []).map((team) => `
    <a class="div-card" href="${teamHref(team.abbr)}">
      <img src="${esc(team.logo)}" alt="" />
      <div>
        <strong>${esc(team.name)}</strong>
        <div class="meta">${esc(team.division)} · ${esc(team.record)} · ${esc(team.points)} pts · ${esc(signed(team.diff))}</div>
      </div>
    </a>
  `).join("");
}

function trendCard(team) {
  const direction = team.formDirection || "flat";
  return `<a class="trend-team ${esc(direction)}" href="${teamHref(team.abbr)}">
    <img src="${esc(team.logo)}" alt="" />
    <div>
      <strong>${esc(team.name)}</strong>
      <div class="meta">${esc(team.record)} · last 3 ${esc(team.formRecord || "—")} · ${esc(team.streak || "—")}</div>
    </div>
    <div class="delta">${esc(signed(team.formDiff))} ${trendBadge(direction)}</div>
  </a>`;
}

function renderTrending(data) {
  $("trendingBlurb").textContent = data.trendingBlurb || "";
  const trending = data.trending || {};
  $("trendUp").innerHTML = (trending.up || []).map(trendCard).join("")
    || `<p class="meta">Form shows up after teams play.</p>`;
  $("trendDown").innerHTML = (trending.down || []).map(trendCard).join("")
    || `<p class="meta">Form shows up after teams play.</p>`;
}

function gameCard(game) {
  const side = (entry) => {
    const classes = [
      "side-line",
      entry.winner ? "winner" : "",
      game.completed && entry.winner === false ? "loser" : "",
    ].filter(Boolean).join(" ");
    const right = game.completed || game.live
      ? (entry.score ?? "")
      : (entry.record || "");
    return `<a class="${classes}" href="${teamHref(entry.abbr)}">
      <img src="${esc(entry.logo)}" alt="" />
      <span>${esc(entry.abbr)}</span>
      <span class="pts">${esc(right)}</span>
    </a>`;
  };
  const extra = [
    game.exhibition ? "Exhibition" : "",
    game.completed || game.live ? "" : game.broadcast,
    game.venue,
  ].filter(Boolean).join(" · ");
  return `<article class="game-card${game.live ? " live" : ""}">
    <div class="when">${esc(game.status || "")}</div>
    ${side(game.away || {})}
    ${side(game.home || {})}
    ${extra ? `<div class="venue">${esc(extra)}</div>` : ""}
  </article>`;
}

function renderWeek(data) {
  $("weekBlurb").textContent = data.weekBlurb || "";
  const games = data.thisWeek || [];
  $("weekGames").innerHTML = games.length
    ? games.map(gameCard).join("")
    : `<p class="meta">The slate for this week is not posted yet.</p>`;
}

function renderLast(data) {
  $("lastBlurb").textContent = data.lastBlurb || "";
  const games = data.lastWeek || [];
  $("lastGames").innerHTML = games.length
    ? games.map(gameCard).join("")
    : `<p class="meta">Scores from last week will show up after the first games.</p>`;
}

const MY_TEAMS_KEY = "nhl-push-my-teams";
const MY_TEAM_COUNT = 5;
let leagueData = null;
let myTeamsEditing = false;
let trackedMemory = null;

function trackedTeams() {
  if (trackedMemory) return trackedMemory.slice();
  let saved = [];
  try {
    saved = JSON.parse(localStorage.getItem(MY_TEAMS_KEY) || "[]");
  } catch (err) {
    saved = [];
  }
  if (!Array.isArray(saved)) saved = [];
  const abbrs = Array.from({ length: MY_TEAM_COUNT }, (_, index) => String(saved[index] || "").toUpperCase());
  const seen = new Set();
  return abbrs.map((abbr) => {
    if (!abbr || seen.has(abbr)) return "";
    seen.add(abbr);
    return abbr;
  });
}

function setTracked(abbrs) {
  const seen = new Set();
  const next = Array.from({ length: MY_TEAM_COUNT }, (_, index) => {
    const abbr = String(abbrs[index] || "").toUpperCase();
    if (!abbr || seen.has(abbr)) return "";
    seen.add(abbr);
    return abbr;
  });
  trackedMemory = next;
  try {
    localStorage.setItem(MY_TEAMS_KEY, JSON.stringify(next));
  } catch (err) {
    /* Private browsing can block storage; the in-memory list still works this visit. */
  }
  return next;
}

function teamSelect(rows, tracked, slot) {
  const taken = new Set(tracked.filter((abbr, index) => abbr && index !== slot));
  const ordered = rows.slice().sort((a, b) => a.division.localeCompare(b.division) || a.name.localeCompare(b.name));
  const groups = [];
  ordered.forEach((team) => {
    const last = groups[groups.length - 1];
    if (!last || last.name !== team.division) groups.push({ name: team.division, teams: [team] });
    else last.teams.push(team);
  });
  const options = groups.map((group) => {
    const items = group.teams.map((team) => {
      const disabled = taken.has(team.abbr) ? " disabled" : "";
      const selected = team.abbr === tracked[slot] ? " selected" : "";
      return `<option value="${esc(team.abbr)}"${selected}${disabled}>${esc(team.name)}</option>`;
    }).join("");
    return `<optgroup label="${esc(group.name)}">${items}</optgroup>`;
  }).join("");
  return `<label class="mine-pick">${slot + 1}
    <select data-slot="${slot}" aria-label="Team ${slot + 1}">
      <option value="">Choose a team</option>
      ${options}
    </select>
  </label>`;
}

function renderMyTeams(data) {
  if (!data) return;
  leagueData = data;
  const rows = data.powerRankings || [];
  const byAbbr = Object.fromEntries(rows.map((team) => [team.abbr, team]));
  const tracked = trackedTeams().map((abbr) => (byAbbr[abbr] ? abbr : ""));
  const hasAny = tracked.some(Boolean);
  const editing = myTeamsEditing || !hasAny;
  const button = $("myTeamsEdit");
  if (button) {
    button.hidden = !hasAny;
    button.textContent = editing ? "Done" : "Edit";
    button.setAttribute("aria-expanded", editing ? "true" : "false");
  }
  const body = $("myTeamsBody");
  if (!body) return;
  if (editing) {
    body.innerHTML = `<div class="mine-picks">
      ${Array.from({ length: MY_TEAM_COUNT }, (_, slot) => teamSelect(rows, tracked, slot)).join("")}
      <p class="mine-note">Pick up to five. Saved on this browser.</p>
    </div>`;
    return;
  }
  const cards = tracked.map((abbr, slot) => {
    if (!abbr) {
      return `<button type="button" class="mine-empty" data-slot="${slot}">Pick a team</button>`;
    }
    const team = byAbbr[abbr];
    const direction = team.formDirection || "flat";
    const trend = direction === "up" ? "▲" : direction === "down" ? "▼" : "—";
    const trendWord = direction === "up" ? "up" : direction === "down" ? "down" : "unchanged";
    const summary = `${team.name}, power rank ${team.rank}, trend ${trendWord} over the last three games, ${team.nextLabel || "—"}, magic number ${team.magicValue || "—"}.`;
    return `<a class="mine-row" href="${teamHref(abbr)}" aria-label="${esc(summary)}">
      <img src="${esc(team.logo)}" alt="" />
      <span class="mine-abbr">${esc(abbr)}</span>
      <span class="mine-rank">${esc(team.rank)}</span>
      <span class="mine-trend ${esc(direction)}" title="Last three games are ${esc(trendWord)}">${trend}</span>
      <span class="mine-week" title="${esc(team.nextTitle || "")}">${esc(team.nextLabel || "—")}</span>
      <span class="mine-magic ${esc(team.magicKind || "")}" title="${esc(team.magicTitle || "")}">${esc(team.magicValue || "—")}</span>
    </a>`;
  }).join("");
  body.innerHTML = `<div class="mine-cols" aria-hidden="true"><span></span><span></span><span>Rank</span><span>Trend</span><span>Next</span><span>Magic</span></div>${cards}`;
}

function wireMyTeams() {
  const root = $("myTeams");
  if (!root || root.dataset.wired) return;
  root.dataset.wired = "1";
  root.addEventListener("click", (event) => {
    const edit = event.target.closest("#myTeamsEdit");
    if (edit) {
      myTeamsEditing = edit.textContent !== "Done";
      renderMyTeams(leagueData);
      if (myTeamsEditing) {
        const select = root.querySelector("select");
        if (select) select.focus();
      }
      return;
    }
    const empty = event.target.closest(".mine-empty");
    if (!empty) return;
    myTeamsEditing = true;
    renderMyTeams(leagueData);
    const select = root.querySelector(`select[data-slot="${empty.dataset.slot}"]`);
    if (select) select.focus();
  });
  root.addEventListener("change", (event) => {
    const select = event.target.closest("select[data-slot]");
    if (!select) return;
    const next = trackedTeams();
    next[Number(select.dataset.slot)] = select.value;
    myTeamsEditing = true;
    setTracked(next);
    renderMyTeams(leagueData);
    const fresh = root.querySelector(`select[data-slot="${select.dataset.slot}"]`);
    if (fresh) fresh.focus();
  });
}

async function boot() {
  try {
    const res = await fetch(`data/league.json?t=${Date.now()}`, { cache: "no-store" });
    if (!res.ok) throw new Error("Could not load league.json");
    const data = await res.json();
    renderTicker(data);
    renderHero(data);
    renderMyTeams(data);
    wireMyTeams();
    renderClubs(data);
    renderRankings(data);
    renderPicture(data);
    renderLeaders(data);
    renderTrending(data);
    renderWeek(data);
    renderLast(data);
    bindTermTips();
  } catch (err) {
    const headline = $("headline");
    if (headline) headline.textContent = "The board needs a data refresh";
    const blurb = $("blurb");
    if (blurb) blurb.textContent = "Run scripts/fetch_playoff_data.py, then reload this page.";
    console.error(err);
  }
}

boot();
