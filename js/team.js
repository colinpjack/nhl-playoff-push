let FOCUS = (window.TEAM_PAGE && window.TEAM_PAGE.abbr) || "";

function focusOf(data) {
  return data.focus || {};
}

function renderChrome(data) {
  const focus = focusOf(data);
  const headings = data.headings || {};
  if (focus.name) document.title = `The Push | ${focus.name} Playoff Dashboard`;
  const logo = document.querySelector(".brand-logo");
  if (logo && focus.logo) {
    logo.src = focus.logo;
    logo.alt = focus.name || "";
  }
  const icon = document.querySelector("link[rel='icon']");
  if (icon && focus.logo) icon.href = focus.logo;
  const eyebrow = document.querySelector(".eyebrow");
  if (eyebrow && focus.name) eyebrow.textContent = focus.name;
  const rules = $("rules");
  if (rules) {
    rules.innerHTML = (data.rules || []).map((rule) => `<span class="pill ghost">${esc(rule)}</span>`).join("");
  }
  const text = {
    divisionTitle: headings.division,
    leadersTitle: headings.leaders,
    leadersBlurb: headings.leadersBlurb,
    pathsBlurb: headings.pathsBlurb,
    legendTeam: headings.legendTeam,
    footerLine: headings.footer,
    footerTiny: headings.footerTiny,
    conclusionLede: headings.conclusion,
    rootingBlurb: headings.rootingBlurb,
  };
  Object.entries(text).forEach(([id, value]) => {
    const el = $(id);
    if (el && value) el.textContent = value;
  });
}

function renderTicker(data) {
  const line = (data.ticker || []).join("   •   ") + "   •   ";
  $("tickerTrack").textContent = line + line;
}

function renderConclusion(data) {
  const out = Boolean(data.eliminated);
  document.body.classList.toggle("season-over", out);
  const banner = $("conclusion");
  if (banner) banner.hidden = !out;
  const lede = $("conclusionLede");
  const headings = data.headings || {};
  if (lede && headings.conclusion) lede.textContent = headings.conclusion;
}

function renderHero(data) {
  const narrative = data.narrative || {};
  const meters = data.meters || {};
  const primary = meters.primary || {};
  const third = meters.third || data.magicNumber || {};
  const odds = data.playoffOdds || {};
  const focus = focusOf(data);
  $("statusKicker").textContent = narrative.kicker || "";
  $("headline").textContent = narrative.headline || "";
  $("blurb").textContent = narrative.blurb || "";
  $("primaryLabel").textContent = primary.label || "Points back of the cut line";
  $("primaryGiant").textContent = primary.value ?? "—";
  $("primarySub").textContent = primary.sub || "";
  const heat = primary.heat ?? 0;
  $("heatName").textContent = primary.heatLabel || "Points rate";
  $("heatValue").textContent = primary.heatText || `${heat}`;
  $("heatFill").style.width = `${Math.max(0, Math.min(100, heat))}%`;
  $("heroChips").innerHTML = (data.chips || [])
    .map((chip) => `<div class="chip"><span>${esc(chip.label)}</span><strong>${esc(chip.value)}</strong></div>`)
    .join("");
  const pct = odds.percent;
  $("oddsGiant").textContent = fmtOdds(pct);
  $("oddsLine").textContent = odds.sims
    ? `${Number(odds.sims).toLocaleString("en-US")} sims · ${data.seasonGames || "—"} game schedule`
    : "";
  $("oddsNote").textContent = odds.note || "";
  const oddsCard = document.querySelector(".hero-score.odds");
  if (oddsCard) {
    oddsCard.classList.remove("longshot", "toss-up", "live");
    if (pct == null) {
      /* waiting on the simulation */
    } else if (pct < 25) {
      oddsCard.classList.add("longshot");
    } else if (pct < 45) {
      oddsCard.classList.add("toss-up");
    } else {
      oddsCard.classList.add("live");
    }
  }
  $("magicLabel").textContent = third.label || "Magic number to clinch";
  $("magicGiant").textContent = third.value ?? "—";
  $("magicLine").textContent = third.sub || "";
  $("magicNote").textContent = third.note || "";
  $("updatePill").textContent = `Updated ${relativeTime(data.generatedAt)}`;
  $("seasonPill").textContent = data.eliminated
    ? `${data.season} season over`
    : `${data.season} ${focus.conference || ""}`.trim();
  if (data.legend) {
    $("legendIn").textContent = data.legend.in || "In a playoff spot";
    $("legendOut").textContent = data.legend.out || "Outside";
  }
}

function renderKpis(data) {
  $("kpis").innerHTML = (data.kpis || []).map((kpi) => `
    <article class="kpi">
      <div class="label">${kpi.stat ? term(kpi.stat, kpi.label) : esc(kpi.label)}</div>
      <div class="value">${esc(kpi.value)}</div>
      <div class="hint">${esc(kpi.hint || "")}</div>
    </article>
  `).join("");
}

function renderTrends(data) {
  const preview = data.mode === "preview";
  const focus = focusOf(data);
  $("trendBlurb").textContent = preview
    ? `Where the ${focus.nickname || "club"} stood at the end of ${data.timeframe}.`
    : "The gaps that decide April, and whether the points are coming at home or on the road.";
  $("trends").innerHTML = (data.trends || []).map((card) => `
    <article class="trend-card ${esc(card.direction || "flat")}">
      <div class="label">${card.stat ? term(card.stat, card.label) : esc(card.label)}</div>
      <div class="value">${esc(card.value)} ${trendBadge(card.direction)}</div>
      <div class="hint">${esc(card.detail || "")}</div>
    </article>
  `).join("");
}

function renderPaths(data) {
  $("paths").innerHTML = ["division", "wildcard"].map((key) => {
    const path = (data.paths || {})[key] || {};
    return `<article class="path-card${path.in ? " in-path" : ""}">
      <h4>${esc(path.title || "")}</h4>
      <div class="path-num">${esc(path.value || "—")}</div>
      <p class="meta">${esc(path.detail || "")}</p>
    </article>`;
  }).join("");
}

function renderConference(data) {
  const preview = data.mode === "preview";
  $("tableBlurb").textContent = data.tableBlurb || "";
  const series = data.seriesLabel || "Series";
  const head = preview
    ? ["#", "Team", term("Path", "Path"), term("W-L-OT", "W-L-OT"), term("PTS"), term("PTS%"), term("RW"), term("Diff", "Diff"), term("Series", series)]
    : ["#", "Team", term("Path", "Path"), term("GP"), term("W-L-OT", "W-L-OT"), term("PTS"), term("PTS%"), term("RW"), term("Diff", "Diff"), term("L10"), term("GR")];
  document.querySelector("#conferenceTable thead").innerHTML = headerRow(head);
  document.querySelector("#conferenceTable tbody").innerHTML = (data.conference || []).map((team) => {
    const classes = [
      team.inField ? "row-in" : "",
      team.isFocus ? "row-jays" : "",
      team.isCut ? "row-cut" : "",
    ].filter(Boolean).join(" ");
    const cut = team.isCut ? `<div class="cut-note">Last berth</div>` : "";
    const tail = preview
      ? `<td>${team.isFocus ? "—" : esc(team.vsFocus ?? 0)}</td>`
      : `<td>${esc(team.l10 || "—")}</td><td>${esc(team.gr ?? "—")}</td>`;
    return `<tr class="${classes}">
      <td>${esc(team.rank)}${cut}</td>
      <td>${teamCell(team)}${team.isFocus ? " ★" : ""}</td>
      <td>${esc(team.path)}</td>
      ${preview ? "" : `<td>${esc(team.gp)}</td>`}
      <td>${esc(team.record)}</td>
      <td>${esc(team.points)}</td>
      <td>${esc(ptsPct(team.pointPct))}</td>
      <td>${esc(team.rw)}</td>
      <td>${esc(signed(team.diff))}</td>
      ${tail}
    </tr>`;
  }).join("");
}

function renderDivision(data) {
  const preview = data.mode === "preview";
  const head = preview
    ? ["#", "Team", term("W-L-OT", "W-L-OT"), term("PTS"), term("RW"), "Home", "Road", term("Series", data.seriesLabel || "Series")]
    : ["#", "Team", term("GP"), term("W-L-OT", "W-L-OT"), term("PTS"), term("PTS%"), term("RW"), term("GR")];
  document.querySelector("#divisionTable thead").innerHTML = headerRow(head);
  document.querySelector("#divisionTable tbody").innerHTML = (data.divisionTable || []).map((team) => {
    const classes = [
      team.divisionRank <= 3 ? "row-in" : "",
      team.isFocus ? "row-jays" : "",
      team.divisionCut ? "row-cut" : "",
    ].filter(Boolean).join(" ");
    const cut = team.divisionCut ? `<div class="cut-note">Auto berth</div>` : "";
    const tail = preview
      ? `<td>${esc(team.home)}</td><td>${esc(team.road)}</td><td>${team.isFocus ? "—" : esc(team.vsFocus ?? 0)}</td>`
      : `<td>${esc(ptsPct(team.pointPct))}</td><td>${esc(team.rw)}</td><td>${esc(team.gr ?? "—")}</td>`;
    const mid = preview
      ? `<td>${esc(team.record)}</td><td>${esc(team.points)}</td><td>${esc(team.rw)}</td>`
      : `<td>${esc(team.gp)}</td><td>${esc(team.record)}</td><td>${esc(team.points)}</td>`;
    return `<tr class="${classes}">
      <td>${esc(team.divisionRank)}${cut}</td>
      <td>${teamCell(team)}</td>
      ${mid}
      ${tail}
    </tr>`;
  }).join("");
}

function renderLeaders(data) {
  $("divLeaders").innerHTML = (data.leaders || []).map((team) => `
    <a class="div-card" href="${teamHref(team.abbr)}">
      <img src="${esc(team.logo)}" alt="" />
      <div>
        <strong>${esc(team.name)}</strong>
        <div class="meta">${esc(team.division)} · ${esc(team.record)} · ${esc(team.points)} pts · ${esc(ptsPct(team.pointPct))}</div>
      </div>
    </a>
  `).join("");
}

function metricMax(rows, getter) {
  return Math.max(...rows.map((row) => getter(row)), 0.0001);
}

function compareBlock(rows, block) {
  const max = metricMax(rows, block.get);
  const sorted = [...rows].sort((a, b) => block.get(b) - block.get(a));
  const body = sorted.map((team) => {
    const width = Math.max(8, Math.min(100, Math.round((block.get(team) / max) * 100)));
    return `<div class="compare-row">
      <a class="who" href="${teamHref(team.abbr)}"><img src="${esc(team.logo)}" alt="" />${esc(team.abbr)}</a>
      <div class="bar ${team.abbr === FOCUS ? "jays" : ""}"><span style="width:${width}%"></span></div>
      <b>${esc(block.format(team))}</b>
    </div>`;
  }).join("");
  return `<div class="compare-block"><header>${block.title}</header>${body}</div>`;
}

function renderCompare(data) {
  $("compareTitle").textContent = data.compareTitle || "Teams in the division";
  const rows = data.compare || [];
  const columns = [
    {
      heading: "The standings",
      blocks: [
        { title: term("PTS"), get: (team) => team.points || 0, format: (team) => team.points },
        { title: term("RW"), get: (team) => team.rw || 0, format: (team) => team.rw },
        { title: term("ROW"), get: (team) => team.row || 0, format: (team) => team.row },
      ],
    },
    {
      heading: "The margins",
      blocks: [
        { title: term("Diff", "Goal diff"), get: (team) => (team.diff || 0) + 200, format: (team) => signed(team.diff) },
        { title: "Home points", get: (team) => team.homePoints || 0, format: (team) => team.homePoints },
        { title: "Road points", get: (team) => team.roadPoints || 0, format: (team) => team.roadPoints },
      ],
    },
  ];
  $("compare").innerHTML = columns.map((col) => `
    <div class="compare-col">
      <h4>${col.heading}</h4>
      ${col.blocks.map((block) => compareBlock(rows, block)).join("")}
    </div>
  `).join("");
}

function renderSchedule(data) {
  const focus = focusOf(data);
  const nick = focus.nickname || focus.abbr || "Team";
  const left = data.remaining || {};
  const sos = left.sos == null ? "—" : ptsPct(left.sos);
  $("gauntletBlurb").textContent =
    `${left.games || 0} games left · ${left.home || 0} home · ${left.away || 0} road · ` +
    `${left.division || 0} against the ${focus.division || "division"} · ${left.backToBacks || 0} back-to-backs · ` +
    `opponent strength ${sos}.`;
  const today = new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/New_York", year: "numeric", month: "2-digit", day: "2-digit",
  }).format(new Date());
  $("tickets").innerHTML = (data.schedule || []).map((game) => {
    const opp = game.opponent || {};
    const isToday = game.date === today;
    const score = game.final
      ? `${game.result || ""} ${game.usScore}–${game.themScore}`
      : (game.venue || "");
    const tags = [
      game.divisionGame ? (focus.division || "Division") : (game.conferenceGame ? (focus.conference || "Conference") : "Interconference"),
      game.backToBack ? "Back-to-back" : "",
      opp.pointPct != null ? `Opp ${ptsPct(opp.pointPct)}` : "",
    ].filter(Boolean).join(" · ");
    const odds = game.final || game.winPct == null
      ? ""
      : `<div class="ticket-odds"><div class="split-odds">${esc(nick)} ${esc(game.winPct)}%</div></div>`;
    const oppLink = opp.abbr
      ? `<a href="${teamHref(opp.abbr)}">${esc(opp.abbr)}</a>`
      : "TBD";
    return `<article class="ticket${isToday ? " today" : ""}">
      <div class="when">${esc(fmtDate(game.start || game.date, Boolean(game.start)))}</div>
      <h4>${game.isHome ? "vs" : "@"} ${oppLink}</h4>
      <div class="pitch">${esc(tags)}</div>
      ${odds}
      <div class="venue">${esc(score)}</div>
    </article>`;
  }).join("") || `<p class="meta">The remaining schedule is not posted yet.</p>`;
}

function renderPreseason(data) {
  const games = data.preseason || [];
  const panel = $("preseasonPanel");
  if (!games.length) {
    if (panel) panel.hidden = true;
    return;
  }
  if (panel) panel.hidden = false;
  $("preseason").innerHTML = games.map((game) => {
    const opp = game.opponent || {};
    const score = game.final
      ? `${game.result || ""} ${game.usScore}–${game.themScore}`
      : "Does not count";
    const oppLink = opp.abbr
      ? `<a href="${teamHref(opp.abbr)}">${esc(opp.abbr)}</a>`
      : "";
    return `<article class="ticket">
      <div class="when">${esc(fmtDate(game.start || game.date, Boolean(game.start)))}</div>
      <h4>${game.isHome ? "vs" : "@"} ${oppLink}</h4>
      <div class="pitch">Exhibition</div>
      <div class="venue">${esc(score)}</div>
    </article>`;
  }).join("");
}

function renderRooting(data) {
  const games = data.rooting || [];
  $("rooting").innerHTML = games.length
    ? games.map((game) => `
      <article class="root-card">
        <div class="root-head">
          <span class="tag ${esc(game.tagClass || "race")}">${esc(game.interest || "Game")}</span>
        </div>
        <strong><a href="${teamHref(game.awayAbbr)}">${esc(game.awayAbbr)}</a> @ <a href="${teamHref(game.homeAbbr)}">${esc(game.homeAbbr)}</a></strong>
        <div class="meta">${esc(fmtDate(game.start || game.date, Boolean(game.start)))}${game.backToBack ? " · second of a back-to-back" : ""}</div>
        <div class="score">${esc(game.awayAbbr)} ${esc(game.awayWinPct)}% · ${esc(game.homeAbbr)} ${esc(game.homeWinPct)}%</div>
        <p>${esc(game.note || "")}</p>
      </article>
    `).join("")
    : `<p class="meta">No games in the next stretch change the picture.</p>`;
}

function renderResults(data) {
  $("recentBlurb").textContent = data.recentBlurb || "";
  const games = data.recent || [];
  if (!games.length) {
    $("results").innerHTML = `<li><span></span><span>Regular-season results land here after opening night.</span><strong></strong></li>`;
    return;
  }
  $("results").innerHTML = games.slice().reverse().map((game) => {
    const opp = game.opponent || {};
    const mark = game.result || "•";
    const who = opp.abbr
      ? `<a href="${teamHref(opp.abbr)}">${esc(opp.abbr)}</a>`
      : "";
    return `<li>
      <span class="badge ${esc(mark)}">${esc(mark === "OTL" ? "OT" : mark)}</span>
      <span>${game.isHome ? "vs" : "@"} ${who} · ${esc(fmtDate(game.date))}</span>
      <strong>${esc(game.usScore)}–${esc(game.themScore)}</strong>
    </li>`;
  }).join("");
}

function renderTiebreak(data) {
  const box = data.tiebreak || {};
  $("tiebreak").innerHTML = `
    <div class="kpis" style="margin:0">
      <article class="kpi"><div class="label">${term("RW")}</div><div class="value">${esc(box.rw ?? "—")}</div><div class="hint">Regulation wins</div></article>
      <article class="kpi"><div class="label">${term("ROW")}</div><div class="value">${esc(box.row ?? "—")}</div><div class="hint">${esc(box.otWins ?? 0)} overtime wins inside that</div></article>
      <article class="kpi"><div class="label">OT losses</div><div class="value">${esc(box.otl ?? "—")}</div><div class="hint">One point each</div></article>
      <article class="kpi"><div class="label">SO wins</div><div class="value">${esc(box.soWins ?? "—")}</div><div class="hint">Points, but not a tiebreaker win</div></article>
    </div>
    <p class="lede">${esc(box.detail || "")}</p>
  `;
}

function skaterCard(player) {
  const points = player.points == null ? "—" : player.points;
  const line = player.gp
    ? `${player.position || ""} · ${player.gp} GP · ${player.goals}G ${player.assists}A · ${signed(player.plusMinus)} · ${player.toi} TOI`
    : `${player.position || ""} · no games in this sample`;
  return `<article class="player">
    <img src="${esc(player.headshot)}" alt="" onerror="this.style.opacity='0.25'" />
    <div>
      <strong>${esc(player.name)}</strong>
      <div class="meta">${esc(line)}</div>
    </div>
    <div class="statline"><span class="statline-value">${esc(points)}</span><span class="statline-label">${term("PTS")}</span></div>
  </article>`;
}

function renderPlayers(data) {
  const players = data.players || {};
  const note = players.label || "";
  if ($("forwardBlurb")) {
    $("forwardBlurb").textContent = note || "Current roster. Points are the column that matters.";
  }
  if ($("goalieBlurb")) {
    $("goalieBlurb").textContent = note
      ? `${note} Save percentage first.`
      : "Save percentage first. Goals-against average second. Wins are a team stat wearing a mask.";
  }
  $("forwards").innerHTML = (players.forwards || []).map(skaterCard).join("")
    || `<p class="meta">Roster numbers will show up once the NHL posts them.</p>`;
  $("defense").innerHTML = (players.defense || []).map(skaterCard).join("")
    || `<p class="meta">Blue-line numbers will show up once the NHL posts them.</p>`;
  $("goalies").innerHTML = (players.goalies || []).map((player) => {
    const record = player.gp
      ? `${player.wins ?? 0}-${player.losses ?? 0}-${player.otl ?? 0} · ${player.gp} GP · ${player.so ?? 0} SO`
      : "No games in this sample";
    const sv = player.sv == null ? "—" : ptsPct(player.sv);
    const gaa = player.gaa == null ? "" : `${Number(player.gaa).toFixed(2)} GAA`;
    return `<article class="player">
      <img src="${esc(player.headshot)}" alt="" onerror="this.style.opacity='0.25'" />
      <div>
        <strong>${esc(player.name)}</strong>
        <div class="meta">${esc(record)}${gaa ? ` · ${esc(gaa)}` : ""}</div>
      </div>
      <div class="statline"><span class="statline-value">${esc(sv)}</span><span class="statline-label">SV%</span></div>
    </article>`;
  }).join("") || `<p class="meta">Goalie numbers will show up once the NHL posts them.</p>`;
}

async function boot() {
  const page = window.TEAM_PAGE || {};
  const slug = String(page.abbr || FOCUS).toLowerCase();
  try {
    const res = await fetch(`${assetRoot()}data/teams/${slug}.json?t=${Date.now()}`, { cache: "no-store" });
    if (!res.ok) throw new Error("Could not load team data");
    const data = await res.json();
    FOCUS = (data.focus && data.focus.abbr) || page.abbr || FOCUS;
    renderChrome(data);
    renderTicker(data);
    renderConclusion(data);
    renderHero(data);
    renderKpis(data);
    renderTrends(data);
    renderPaths(data);
    renderConference(data);
    renderDivision(data);
    renderLeaders(data);
    renderCompare(data);
    renderSchedule(data);
    renderPreseason(data);
    renderRooting(data);
    renderResults(data);
    renderTiebreak(data);
    renderPlayers(data);
    bindTermTips();
  } catch (err) {
    const headline = $("headline");
    if (headline) headline.textContent = "Dashboard needs a data refresh";
    const blurb = $("blurb");
    if (blurb) blurb.textContent = "Run scripts/fetch_playoff_data.py, then reload this page.";
    console.error(err);
  }
}

boot();
