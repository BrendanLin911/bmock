/* Uploader bootstrap and report download.

   This file runs only on the live page. It is deliberately NOT part of
   app.js: app.js is inlined verbatim into every saved report, and anything
   in it that touches the network would ship into a file:// document where
   fetch is blocked outright.

   The download is built here, in the browser, from the payload the page
   already holds. The server keeps nothing, so there is nothing for it to
   re-send: your PDF is scored in memory and dropped. */
(function () {
  "use strict";

  var drop = document.getElementById("drop");
  var input = document.getElementById("file");
  var status = document.getElementById("status");
  var report = document.getElementById("report");
  var uploader = document.getElementById("uploader");
  var fname = document.getElementById("fname");
  var again = document.getElementById("again");
  var dlHtml = document.getElementById("dl-html");
  var dlJson = document.getElementById("dl-json");

  // The exact bytes the server sent, kept so the saved report carries the
  // numbers the user actually read rather than a re-serialized copy.
  var payloadText = null;
  var payloadData = null;
  var assets = null;

  /* Warm the three files the download needs, once, at load. Fetching them
     inside the click handler would break the user-gesture chain, which
     Safari uses to decide whether a programmatic download is allowed. */
  Promise.all([
    fetch("/style.css").then(function (r) { return r.text(); }),
    fetch("/app.js").then(function (r) { return r.text(); }),
    fetch("/report-template.html").then(function (r) { return r.text(); })
  ]).then(function (a) {
    assets = { css: a[0], js: a[1], tpl: a[2] };
  }).catch(function () {
    assets = null;               // download stays hidden; scoring still works
  });

  function setStatus(text, bad) {
    status.textContent = text;
    status.style.color = bad ? "var(--red)" : "";
    status.style.borderColor = bad ? "var(--red)" : "";
  }

  function reset() {
    report.innerHTML = "";
    uploader.hidden = false;
    fname.hidden = true;
    again.hidden = true;
    dlHtml.hidden = true;
    dlJson.hidden = true;
    payloadText = null;
    payloadData = null;
    setStatus("ready");
  }

  // ---------------------------------------------------------------- save
  function saveBlob(text, type, filename) {
    var url = URL.createObjectURL(new Blob([text], { type: type }));
    var a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.rel = "noopener";
    a.style.display = "none";
    document.body.appendChild(a);
    a.click();
    a.remove();
    // Revoking synchronously after click() can truncate the download: the
    // browser has not necessarily started reading the blob yet.
    var release = function () { URL.revokeObjectURL(url); };
    setTimeout(release, 60000);
    window.addEventListener("pagehide", release, { once: true });
  }

  function htmlText(s) {
    return String(s === undefined || s === null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  /* Mirrors json_for_script() in report.py. `<`, `>` and `&` cannot occur
     outside a string in JSON, so escaping them makes `</script`, `<!--` and
     `<script` unrepresentable inside the payload. */
  function jsonForScript(text) {
    // \u2028 and \u2029 must be written as escapes, never as literal
    // characters: they are line terminators in JS source, so a raw one inside
    // this regex ends the line and the file stops parsing.
    return text.replace(/[<>&\u2028\u2029]/g, function (c) {
      return "\\u" + ("000" + c.charCodeAt(0).toString(16)).slice(-4);
    });
  }

  function reportFilename(data, ext) {
    var base = String(data.filename || "resume.pdf").split(/[\\/]/).pop()
      .replace(/\.pdf$/i, "")
      .replace(/[\x00-\x1f<>:"/\\|?*]/g, "_")
      .replace(/\s+/g, " ").trim()
      .replace(/^\.+/, "_")
      .slice(0, 80);
    if (!base || /^(con|prn|aux|nul|com[1-9]|lpt[1-9])$/i.test(base)) base = "resume";
    var d = new Date(), p = function (n) { return ("0" + n).slice(-2); };
    return base + "-score-" + Math.round(data.overall) + "-" +
      d.getFullYear() + p(d.getMonth() + 1) + p(d.getDate()) + "-" +
      p(d.getHours()) + p(d.getMinutes()) + "." + ext;
  }

  function buildReport() {
    var parts = {
      CSS: assets.css,
      JS: assets.js,
      DATA: jsonForScript(payloadText),
      FILENAME: htmlText(payloadData.filename)
    };
    // A replacer function, never a replacement string: `$&` and "$`" are
    // special in String.replace, and resumes are full of dollar signs.
    return assets.tpl.replace(/\{\{(CSS|JS|DATA|FILENAME)\}\}/g, function (_, key) {
      return parts[key];
    });
  }

  dlHtml.addEventListener("click", function () {
    if (!payloadText || !assets) return;
    saveBlob(buildReport(), "text/html;charset=utf-8", reportFilename(payloadData, "html"));
  });

  dlJson.addEventListener("click", function () {
    if (!payloadText) return;
    saveBlob(payloadText, "application/json", reportFilename(payloadData, "json"));
  });

  again.addEventListener("click", reset);

  // --------------------------------------------------------------- score
  function send(file) {
    if (!file) return;
    if (!/\.pdf$/i.test(file.name)) { setStatus("PDF files only", true); return; }
    drop.classList.add("busy");
    setStatus("scoring …");
    var fd = new FormData();
    fd.append("file", file, file.name);
    fd.append("quirks", document.getElementById("quirks").checked ? "1" : "0");

    fetch("/api/score", { method: "POST", body: fd })
      .then(function (r) {
        return r.text().then(function (t) { return { ok: r.ok, text: t }; });
      })
      .then(function (res) {
        drop.classList.remove("busy");
        var data;
        try {
          data = JSON.parse(res.text);
        } catch (e) {
          setStatus("the server returned something unreadable", true);
          return;
        }
        if (!res.ok || data.error) { setStatus(data.error || "failed", true); return; }

        payloadText = res.text;
        payloadData = data;
        setStatus(data.overall + " / 100");
        fname.textContent = data.filename;
        fname.hidden = false;
        again.hidden = false;
        dlJson.hidden = false;
        dlHtml.hidden = !assets;
        uploader.hidden = true;
        window.VMockReport.render(data, report);
        window.scrollTo(0, 0);
      })
      .catch(function (err) {
        drop.classList.remove("busy");
        setStatus(String(err && err.message ? err.message : err), true);
      });
  }

  drop.addEventListener("click", function () { input.click(); });
  input.addEventListener("change", function () { send(input.files[0]); });
  ["dragenter", "dragover"].forEach(function (ev) {
    drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.add("over"); });
  });
  ["dragleave", "drop"].forEach(function (ev) {
    drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.remove("over"); });
  });
  drop.addEventListener("drop", function (e) {
    e.preventDefault();
    send(e.dataTransfer.files && e.dataTransfer.files[0]);
  });
})();
