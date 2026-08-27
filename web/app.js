/* Renderer shared by the local web app and the static CLI report.

   Layout follows VMock's SMART Resume screen: the page you uploaded on the
   left with feedback pinned to the line that earned it, and the score panel
   on the right - dial, zone band, peer curve, then the three modules as
   accordions over their sub-parameters. */
(function (global) {
  "use strict";

  var ZONE = { red: "--red", yellow: "--yellow", green: "--green" };
  var SEV = { error: "--red", warn: "--yellow", info: "--info", good: "--green" };

  function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || "#888";
  }
  function el(tag, cls, txt) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (txt !== undefined && txt !== null) n.textContent = String(txt);
    return n;
  }
  function esc(s) { return String(s === undefined || s === null ? "" : s); }
  function pct(x) { return Math.max(0, Math.min(100, x)); }
  function sevRank(s) { return s === "error" ? 0 : s === "warn" ? 1 : s === "info" ? 2 : 3; }

  /* Per-render cross-links between the page overlay and the feedback list. */
  function newState() {
    return { pins: {}, marks: {}, rows: {}, order: {}, active: null };
  }

  // ---------------------------------------------------------------- score
  function dial(score, max, zone) {
    var color = cssVar(ZONE[zone] || "--info");
    var R = 62, C = 2 * Math.PI * R, frac = max ? score / max : 0;
    var wrap = el("div", "dial");
    wrap.innerHTML =
      '<svg viewBox="0 0 148 148" width="148" height="148">' +
      '<circle cx="74" cy="74" r="' + R + '" fill="none" stroke="' + cssVar("--line-2") + '" stroke-width="11"/>' +
      '<circle cx="74" cy="74" r="' + R + '" fill="none" stroke="' + color +
      '" stroke-width="11" stroke-linecap="round" stroke-dasharray="' + C +
      '" stroke-dashoffset="' + (C * (1 - frac)) + '" transform="rotate(-90 74 74)"/></svg>';
    var v = el("div", "val");
    var n = el("div", "num", Math.round(score));
    n.style.color = color;
    v.appendChild(n);
    v.appendChild(el("div", "den", "OUT OF " + max));
    wrap.appendChild(v);
    return wrap;
  }

  /* The tri-band meter: where your score sits inside VMock's own cutoffs. */
  function zoneBar(data) {
    var zones = (data.meta && data.meta.zones) ||
      { red: [0, 32], yellow: [33, 85], green: [86, 100] };
    var order = ["red", "yellow", "green"];
    var wrap = el("div", "zonebar");

    var cur = el("div", "cursor");
    var tag = el("i", null, Math.round(data.overall));
    tag.style.left = pct(data.overall) + "%";
    tag.style.color = cssVar(ZONE[data.zone] || "--info");
    cur.appendChild(tag);
    wrap.appendChild(cur);

    var track = el("div", "track");
    order.forEach(function (z) {
      var r = zones[z] || [0, 0];
      var seg = el("i");
      seg.style.width = (r[1] - r[0] + 1) + "%";
      seg.style.background = cssVar(ZONE[z]);
      seg.style.opacity = z === data.zone ? "1" : ".38";
      track.appendChild(seg);
    });
    wrap.appendChild(track);

    var ticks = el("div", "ticks");
    order.forEach(function (z) {
      var r = zones[z] || [0, 0];
      var t = el("span", null, r[0] + "–" + r[1]);
      t.style.width = (r[1] - r[0] + 1) + "%";
      ticks.appendChild(t);
    });
    wrap.appendChild(ticks);
    return wrap;
  }

  function scoreHead(data) {
    var head = el("div", "score-head");
    var row = el("div", "dialrow");
    row.appendChild(dial(data.overall, 100, data.zone));

    var right = el("div");
    right.appendChild(el("div", "score-title", "Resume Score"));
    var zn = el("div", "zone-name", (data.zone || "").replace(/^./, function (c) { return c.toUpperCase(); }) + " Zone");
    zn.style.color = cssVar(ZONE[data.zone] || "--info");
    right.appendChild(zn);

    var bm = data.benchmark || {};
    var note = data.zone === "green"
      ? "Interview-ready by VMock's cutoffs."
      : data.zone === "yellow"
        ? "Above the danger line, below the green cutoff of 86."
        : "Below VMock's red-zone cutoff of 33.";
    if (bm.percentile !== undefined && bm.percentile !== null) {
      note += " Stronger than " + bm.percentile + "% of the " + (bm.label || "cohort") + ".";
    }
    right.appendChild(el("div", "zone-note", note));
    row.appendChild(right);
    head.appendChild(row);
    head.appendChild(zoneBar(data));
    return head;
  }

  // ----------------------------------------------------------- left pane
  /* One pin per annotated line, numbered in reading order. */
  function collectPins(data) {
    var byLine = {};
    (data.modules || []).forEach(function (m) {
      walkSubs(m.subscores || [], function (s) {
        (s.findings || []).forEach(function (f) {
          if (f.line_index === null || f.line_index === undefined) return;
          if (f.severity === "good") return;
          var k = String(f.line_index);
          (byLine[k] = byLine[k] || []).push({ f: f, sub: s.label, mod: m.label });
        });
      });
    });
    var bullets = data.bullets || [];
    var keys = Object.keys(byLine).sort(function (a, b) {
      var A = bullets[a] || {}, B = bullets[b] || {};
      return (A.page - B.page) || (A.top - B.top) || (a - b);
    });
    var out = {};
    keys.forEach(function (k, i) {
      var items = byLine[k].sort(function (x, y) { return sevRank(x.f.severity) - sevRank(y.f.severity); });
      out[k] = { n: i + 1, severity: items[0].f.severity, items: items };
    });
    return out;
  }

  function walkSubs(subs, fn) {
    (subs || []).forEach(function (s) {
      fn(s);
      walkSubs(s.children || [], fn);
    });
  }

  function paperPane(data, state) {
    var pane = el("div", "paper-pane");
    var head = el("div", "paper-head");
    head.appendChild(el("span", null, "Your resume"));
    var legend = el("div", "legend");
    [["error", "costs points"], ["warn", "worth fixing"], ["good", "clean"]].forEach(function (p) {
      var s = el("span");
      var i = el("i");
      i.style.background = cssVar(SEV[p[0]]);
      s.appendChild(i);
      s.appendChild(document.createTextNode(p[1]));
      legend.appendChild(s);
    });
    head.appendChild(legend);
    pane.appendChild(head);

    var pv = data.preview;
    var bullets = data.bullets || [];
    var pins = state.order;

    if (pv && pv.pages && pv.pages.length) {
      pv.pages.forEach(function (pg) {
        var page = el("div", "page");
        var img = el("img");
        img.src = pg.png;
        img.alt = "Resume page " + (pg.index + 1);
        page.appendChild(img);

        bullets.forEach(function (b) {
          if ((b.page - 1) !== pg.index) return;
          var meta = pins[String(b.index)];
          var sev = meta ? meta.severity : "good";
          var mark = el("div", "mark sev-" + sev);
          mark.style.left = (b.x0 / pg.w_pt * 100) + "%";
          mark.style.top = (b.top / pg.h_pt * 100) + "%";
          mark.style.width = ((b.x1 - b.x0) / pg.w_pt * 100) + "%";
          mark.style.height = ((b.bottom - b.top) / pg.h_pt * 100) + "%";
          mark.title = b.text;
          mark.addEventListener("click", function () { focusLine(state, b.index, "paper"); });
          page.appendChild(mark);
          state.marks[b.index] = mark;

          if (meta) {
            var pin = el("div", "pin sev-" + sev, meta.n);
            pin.style.left = Math.max(1.4, (b.x0 / pg.w_pt * 100) - 3.4) + "%";
            pin.style.top = ((b.top + b.bottom) / 2 / pg.h_pt * 100) + "%";
            pin.style.transform = "translate(-50%, -50%)";
            pin.title = meta.items[0].f.message;
            pin.addEventListener("click", function () { focusLine(state, b.index, "paper"); });
            page.appendChild(pin);
            state.pins[b.index] = pin;
          }
        });
        pane.appendChild(page);
      });
      var lbl = el("div", "note");
      lbl.style.textAlign = "center";
      lbl.textContent = pv.pages.length + (pv.pages.length === 1 ? " page" : " pages") +
        "  ·  numbered marks are the lines the score reacted to";
      pane.appendChild(lbl);
    } else {
      // No raster available: fall back to the parsed text, same anchors.
      var page2 = el("div", "page");
      var box = el("div", "no-raster");
      var lines = (pv && pv.lines) || [];
      if (lines.length) {
        box.textContent = lines.map(function (l) { return (l.bullet ? "  • " : "") + l.text; }).join("\n");
      } else {
        box.textContent = bullets.map(function (b) { return "• " + b.text; }).join("\n\n") ||
          "No page preview available.";
      }
      page2.appendChild(box);
      pane.appendChild(page2);
    }
    return pane;
  }

  /* Run after the browser has re-laid-out. Opening an accordion or switching a
     tab changes geometry, and scrolling in the same task measures the OLD
     positions -- which is how a row ends up parked off the bottom of the pane.
     Two frames: one for style, one for layout. */
  function afterLayout(fn) {
    requestAnimationFrame(function () { requestAnimationFrame(fn); });
  }

  /* Scroll a node into the middle of ITS OWN pane.

     scrollIntoView walks every scrollable ancestor, the document included, so
     on a tall report it drags the whole window and leaves the row outside the
     viewport. Only the pane should move. Below 1080px the panes are
     overflow:visible and the window is the scroller, so defer to the native
     call there. */
  function scrollWithin(node) {
    var box = node.closest ? node.closest(".analysis, .paper-pane") : null;
    if (!box || box.scrollHeight <= box.clientHeight + 4) {
      node.scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }
    var delta = node.getBoundingClientRect().top - box.getBoundingClientRect().top;
    var centred = box.scrollTop + delta - (box.clientHeight - node.offsetHeight) / 2;
    box.scrollTo({ top: Math.max(0, centred), behavior: "smooth" });
  }

  /* A finding can live in a tab that is not on screen. A display:none node has
     no position to scroll to, so show its tab first. */
  function revealTab(node) {
    var pane = node.closest ? node.closest(".tabpane[data-tab]") : null;
    if (!pane || pane.classList.contains("on")) return;
    var host = pane.parentElement;
    if (!host) return;
    host.querySelectorAll(".tabpane[data-tab]").forEach(function (p) {
      p.classList.remove("on");
    });
    pane.classList.add("on");
    var tabs = host.querySelector(".tabs");
    if (!tabs) return;
    tabs.querySelectorAll(".tab").forEach(function (b) {
      b.classList.toggle("on", b.dataset.tab === pane.dataset.tab);
    });
  }

  function openAncestors(node) {
    var d = node.closest ? node.closest("details") : null;
    while (d) {
      d.open = true;
      d = d.parentElement && d.parentElement.closest
        ? d.parentElement.closest("details") : null;
    }
  }

  /* Prefer a row already in the open tab, so clicking a line does not yank the
     reader out of whatever they were reading. */
  function pickRow(rows) {
    for (var i = 0; i < rows.length; i++) {
      var pane = rows[i].closest ? rows[i].closest(".tabpane") : null;
      if (!pane || pane.classList.contains("on")) return rows[i];
    }
    return rows[0];
  }

  /* Selecting a line highlights it on the page and its feedback rows. */
  function focusLine(state, idx, from) {
    var prev = state.active;
    if (prev !== null && prev !== undefined) {
      [state.pins[prev], state.marks[prev]].forEach(function (n) { if (n) n.classList.remove("active"); });
      (state.rows[prev] || []).forEach(function (n) { n.classList.remove("active"); });
    }
    if (prev === idx) { state.active = null; return; }
    state.active = idx;
    [state.pins[idx], state.marks[idx]].forEach(function (n) { if (n) n.classList.add("active"); });
    var rows = state.rows[idx] || [];
    rows.forEach(function (n) { n.classList.add("active"); });
    if (from === "paper" && rows.length) {
      // Open every accordion holding a linked row, so picking a line on the
      // page reveals all of its feedback rather than just the top one.
      rows.forEach(openAncestors);
      var target = pickRow(rows);
      revealTab(target);
      afterLayout(function () { scrollWithin(target); });
    } else if (from !== "paper" && state.marks[idx]) {
      var mark = state.marks[idx];
      afterLayout(function () { scrollWithin(mark); });
    }
  }

  function registerRow(state, idx, node) {
    if (idx === null || idx === undefined) return;
    (state.rows[idx] = state.rows[idx] || []).push(node);
    node.classList.add("clickable");
    node.addEventListener("click", function (e) {
      e.stopPropagation();
      focusLine(state, idx, "list");
    });
  }

  // ------------------------------------------------------------ findings
  function findingNode(f, state) {
    var row = el("div", "finding");
    var meta = state.order[String(f.line_index)];
    if (meta && f.severity !== "good") {
      var idx = el("div", "idx", meta.n);
      idx.style.background = cssVar(SEV[f.severity] || "--info");
      row.appendChild(idx);
    } else {
      var d = el("div", "dot");
      d.style.background = cssVar(SEV[f.severity] || "--info");
      row.appendChild(d);
    }
    var mid = el("div");
    var msg = el("div", "msg");
    msg.appendChild(document.createTextNode(esc(f.message)));
    if (f.quirk) {
      var q = el("span", "qtag", "VMOCK QUIRK");
      q.title = "Reproduces a documented VMock rule that is arbitrary or buggy. " +
                "Disable it in rules.yaml under quirks." + f.quirk;
      msg.appendChild(q);
    }
    mid.appendChild(msg);
    if (f.evidence) mid.appendChild(el("div", "ev", esc(f.evidence)));
    if (f.fix) mid.appendChild(el("div", "fix", esc(f.fix)));
    row.appendChild(mid);
    if (f.points_lost > 0.01) row.appendChild(el("div", "cost", "-" + f.points_lost.toFixed(1)));
    if (f.line_index !== null && f.line_index !== undefined && f.severity !== "good") {
      registerRow(state, f.line_index, row);
    }
    return row;
  }

  function statusColor(ratio) {
    return ratio >= 0.85 ? cssVar("--green") : ratio >= 0.5 ? cssVar("--yellow") : cssVar("--red");
  }

  function bar(ratio, color) {
    var b = el("div", "bar"), i = el("i");
    i.style.width = pct(ratio * 100) + "%";
    i.style.background = color;
    b.appendChild(i);
    return b;
  }

  function subNode(s, state) {
    var d = el("details", "sub");
    var sum = el("summary");
    var st = el("div", "status");
    st.style.background = statusColor(s.ratio);
    sum.appendChild(st);
    var lbl = el("div", "lbl");
    lbl.appendChild(document.createTextNode(esc(s.label)));
    var bad = (s.findings || []).filter(function (f) {
      return f.severity === "error" || f.severity === "warn";
    }).length;
    if (bad) lbl.appendChild(el("small", null, bad + (bad === 1 ? " issue" : " issues")));
    sum.appendChild(lbl);
    sum.appendChild(bar(s.ratio, statusColor(s.ratio)));
    sum.appendChild(el("div", "pts", s.points.toFixed(1) + " / " + s.max_points));
    d.appendChild(sum);

    var det = el("div", "detail");
    (s.findings || []).forEach(function (f) { det.appendChild(findingNode(f, state)); });
    (s.children || []).forEach(function (k) { det.appendChild(subNode(k, state)); });
    d.appendChild(det);
    return d;
  }

  function moduleNode(m, state, open) {
    var d = el("details", "mod");
    if (open) d.open = true;
    var sum = el("summary");
    var name = el("div", "mname");
    name.appendChild(el("span", "chev", "▸"));
    name.appendChild(document.createTextNode(esc(m.label)));
    sum.appendChild(name);
    sum.appendChild(el("div", "mpts", m.points.toFixed(1) + " / " + m.max_points));
    var b = bar(m.ratio, statusColor(m.ratio));
    b.classList.add("mbar");
    sum.appendChild(b);
    d.appendChild(sum);

    var inner = el("div", "inner");
    (m.subscores || []).forEach(function (s) { inner.appendChild(subNode(s, state)); });
    (m.findings || []).forEach(function (f) {
      var wrap = el("div", "detail");
      wrap.appendChild(findingNode(f, state));
      inner.appendChild(wrap);
    });
    d.appendChild(inner);
    return d;
  }

  // ------------------------------------------------------------ sub views
  function actionsPanel(data, state) {
    var acts = (data.top_actions || []).filter(function (a) { return a.points > 0.01; });
    if (!acts.length) return null;
    var ol = el("ol", "actions");
    acts.forEach(function (a) {
      var li = el("li");
      li.appendChild(el("span", "gain", "+" + a.points.toFixed(1)));
      var mid = el("div");
      var m = el("div", "amsg");
      m.appendChild(document.createTextNode(esc(a.message)));
      if (a.quirk) {
        var q = el("span", "qtag", "QUIRK");
        q.title = "quirks." + a.quirk + " in rules.yaml";
        m.appendChild(q);
      }
      mid.appendChild(m);
      if (a.fix) mid.appendChild(el("div", "fix", esc(a.fix)));
      li.appendChild(mid);
      if (a.line_index !== null && a.line_index !== undefined) registerRow(state, a.line_index, li);
      ol.appendChild(li);
    });
    return panel("Fix these first", ol);
  }

  function panel(title, node, cls) {
    var p = el("div", "panel" + (cls ? " " + cls : ""));
    if (title) p.appendChild(el("h3", null, title));
    var b = el("div", "body");
    if (node) b.appendChild(node);
    p.appendChild(b);
    return p;
  }

  function sectionsView(data, state) {
    var wrap = el("div");
    var secs = (data.meta && data.meta.sections) || [];
    if (!secs.length) {
      wrap.appendChild(el("div", "note", "No sections were detected."));
      return wrap;
    }
    secs.forEach(function (s) {
      var row = el("div", "secrow");
      var h = el("div", "h");
      h.appendChild(el("b", null, s.heading));
      h.appendChild(el("span", "k", s.canonical || "unrecognised"));
      h.appendChild(el("span", "n", s.bullets + (s.bullets === 1 ? " bullet" : " bullets")));
      row.appendChild(h);
      row.appendChild(el("div", "meta",
        s.entries + (s.entries === 1 ? " entry" : " entries") +
        (s.canonical ? "" : "  ·  not matched to a standard heading, so section-specific rules skip it")));
      wrap.appendChild(row);
    });
    var meta = data.meta || {};
    wrap.appendChild(el("div", "note",
      [meta.pages + (meta.pages === 1 ? " page" : " pages"),
       meta.word_count + " words",
       meta.bullet_count + " scored bullets",
       meta.two_column ? "two-column layout" : null].filter(Boolean).join("  ·  ")));
    return wrap;
  }

  /* Line-level feedback. The side panel is narrow, so each bullet is a card
     rather than a five-column table: text first, verdict underneath. */
  function bulletsList(bullets, state) {
    var wrap = el("div");
    bullets.forEach(function (b) {
      var row = el("div", "blrow");
      var head = el("div", "blhead");
      head.appendChild(el("span", "bln", b.index + 1));
      head.appendChild(el("span", "blsec", b.section));
      var tier = el("span", "chip " +
        (b.verb_tier === "strong" ? "ok" : b.verb_tier === "standard" ? "" :
         b.verb_tier === "weak" ? "warn" : "bad"),
        b.verb ? b.verb + " · " + b.verb_tier : b.verb_tier);
      tier.style.marginLeft = "auto";
      head.appendChild(tier);
      head.appendChild(el("span", "chip " + (b.length_ok ? "ok" : "warn"), b.word_count + "w"));
      row.appendChild(head);
      row.appendChild(el("div", "bltxt", b.text));
      var chips = el("div", "chips");
      if (!b.flags.length) chips.appendChild(el("span", "chip ok", "clean"));
      b.flags.forEach(function (f) {
        chips.appendChild(el("span", "chip " +
          (/no action verb|too long|too short/.test(f) ? "bad" : "warn"), f));
      });
      if (b.quantifiers && b.quantifiers.length)
        chips.appendChild(el("span", "chip ok", "№ " + b.quantifiers.slice(0, 3).join(", ")));
      if (b.tools && b.tools.length)
        chips.appendChild(el("span", "chip ok", b.tools.slice(0, 3).map(function (x) {
          return x.length <= 3 ? x.toUpperCase() : x;
        }).join(", ")));
      row.appendChild(chips);
      registerRow(state, b.index, row);
      wrap.appendChild(row);
    });
    return wrap;
  }

  function bell(data) {
    var bm = data.benchmark || {}, mean = bm.mean || 62, sd = bm.stdev || 14;
    var W = 640, H = 132, pad = 18, padTop = 28;
    function x(v) { return pad + (v / 100) * (W - 2 * pad); }
    function y(v, peak) { return H - pad - (v / peak) * (H - pad - padTop - 8); }
    var pts = [], peak = 0, i;
    for (i = 0; i <= 100; i++) {
      var d = Math.exp(-0.5 * Math.pow((i - mean) / sd, 2));
      peak = Math.max(peak, d);
      pts.push([i, d]);
    }
    var path = pts.map(function (p, k) {
      return (k ? "L" : "M") + x(p[0]).toFixed(1) + " " + y(p[1], peak).toFixed(1);
    }).join(" ");
    var color = cssVar(ZONE[data.zone] || "--info");
    var w = el("div");
    w.innerHTML = '<svg class="bell" viewBox="0 0 ' + W + " " + H + '" preserveAspectRatio="none">' +
      '<path d="' + path + " L" + x(100) + " " + (H - pad) + " L" + x(0) + " " + (H - pad) +
      ' Z" fill="' + cssVar("--line-2") + '"/>' +
      '<path d="' + path + '" fill="none" stroke="' + cssVar("--line") + '" stroke-width="1.5"/>' +
      '<line x1="' + x(mean) + '" y1="' + padTop + '" x2="' + x(mean) + '" y2="' + (H - pad) +
      '" stroke="' + cssVar("--ink-3") + '" stroke-width="1" stroke-dasharray="3 3"/>' +
      '<line x1="' + x(data.overall) + '" y1="' + padTop + '" x2="' + x(data.overall) + '" y2="' + (H - pad) +
      '" stroke="' + color + '" stroke-width="2.5"/>' +
      '<circle cx="' + x(data.overall) + '" cy="' + padTop + '" r="4" fill="' + color + '"/>' +
      '<text x="' + x(mean) + '" y="' + (H - 4) + '" fill="' + cssVar("--ink-3") +
      '" font-size="10" text-anchor="middle">cohort mean ' + mean + '</text>' +
      '<text x="' + x(data.overall) + '" y="' + (padTop - 9) + '" fill="' + color +
      '" font-size="11" font-weight="600" text-anchor="middle">you · ' + Math.round(data.overall) + '</text>' +
      "</svg>";
    var kv = el("div", "kv");
    [["Benchmark", bm.label || bm.name], ["Percentile", bm.percentile + "%"],
     ["vs mean", (bm.delta_from_mean > 0 ? "+" : "") + bm.delta_from_mean],
     ["Cohort size", bm.n || "synthetic"]].forEach(function (p) {
      var s = el("div");
      s.appendChild(document.createTextNode(p[0] + " "));
      s.appendChild(el("b", null, p[1]));
      kv.appendChild(s);
    });
    w.appendChild(kv);
    if (!bm.n) {
      w.appendChild(el("div", "note",
        "Synthetic default curve. VMock benchmarks you against resumes your own institution " +
        "uploaded — build the equivalent with:  python3 -m vmock_clone benchmark ./folder_of_pdfs"));
    }
    return w;
  }

  function quirkPanel(data) {
    var qc = data.quirk_cost || {};
    var keys = Object.keys(qc);
    if (!keys.length) return null;
    var qn = el("div");
    var total = keys.reduce(function (a, k) { return a + qc[k]; }, 0);
    qn.appendChild(el("div", null,
      "You are losing " + total.toFixed(1) + " points to rules that reproduce real VMock behaviour " +
      "but are arbitrary or documented as buggy."));
    var ul = el("ul");
    ul.style.margin = "9px 0 0"; ul.style.paddingLeft = "18px";
    keys.sort(function (a, b) { return qc[b] - qc[a]; }).forEach(function (k) {
      var li = el("li");
      li.appendChild(el("code", null, "quirks." + k));
      li.appendChild(document.createTextNode("  −" + qc[k].toFixed(1)));
      ul.appendChild(li);
    });
    qn.appendChild(ul);
    qn.appendChild(el("div", "note",
      "Set quirks.strict_vmock_quirks: false in rules.yaml to drop all of them."));
    return panel("Quirk cost", qn);
  }

  // ------------------------------------------------------------ analysis
  function analysisPane(data, state) {
    var pane = el("div", "analysis");
    pane.appendChild(scoreHead(data));

    if (data.blockers && data.blockers.length) {
      var bl = el("div");
      data.blockers.forEach(function (b) { bl.appendChild(el("div", "err", b)); });
      bl.appendChild(el("div", "note",
        "The score is still computed so you can work, but VMock itself would refuse to return one."));
      var wrapBlock = el("div", "tabpane on");
      wrapBlock.appendChild(panel("Blocked", bl, "alarm"));
      pane.appendChild(wrapBlock);
    }

    var tabs = el("div", "tabs");
    var panes = [];
    var defs = [
      ["Overall", function () {
        var w = el("div");
        var acts = actionsPanel(data, state);
        if (acts) w.appendChild(acts);
        (data.modules || []).forEach(function (m, i) {
          w.appendChild(moduleNode(m, state, i === 0));
        });
        w.appendChild(panel("Peer benchmark", bell(data)));
        var q = quirkPanel(data);
        if (q) w.appendChild(q);
        return w;
      }],
      ["Section-wise", function () { return sectionsView(data, state); }],
      ["Line-by-line", function () {
        return (data.bullets || []).length
          ? bulletsList(data.bullets, state)
          : el("div", "note", "No bullets were detected.");
      }],
    ];
    defs.forEach(function (d, i) {
      var b = el("button", "tab" + (i === 0 ? " on" : ""), d[0]);
      var p = el("div", "tabpane" + (i === 0 ? " on" : ""));
      // Pair them, so focusLine can raise the tab holding a finding. The
      // "Blocked" pane above carries no data-tab and is never a tab.
      b.dataset.tab = p.dataset.tab = String(i);
      p.appendChild(d[1]());
      b.addEventListener("click", function () {
        tabs.querySelectorAll(".tab").forEach(function (t) { t.classList.remove("on"); });
        panes.forEach(function (x) { x.classList.remove("on"); });
        b.classList.add("on");
        p.classList.add("on");
      });
      tabs.appendChild(b);
      panes.push(p);
    });
    pane.appendChild(tabs);
    panes.forEach(function (p) { pane.appendChild(p); });

    var meta = data.meta || {};
    var f = el("div", "foot");
    f.appendChild(el("div", null, data.filename + "  ·  " + data.generated_at));
    f.appendChild(el("div", null, "Rules: " +
      String(meta.rules_file || "rules.yaml").split(/[\\/]/).pop() +
      "  ·  quirks " + (meta.quirks_enabled ? "on" : "off") + "  ·  no language model involved"));
    pane.appendChild(f);
    return pane;
  }

  // ---------------------------------------------------------------- entry
  function render(data, root) {
    root.innerHTML = "";
    var state = newState();
    state.order = collectPins(data);
    var app = el("div", "app");
    app.appendChild(paperPane(data, state));
    app.appendChild(analysisPane(data, state));
    root.appendChild(app);
  }

  global.VMockReport = { render: render };
})(window);
