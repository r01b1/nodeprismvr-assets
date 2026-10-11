// Review page: lists open pull requests that add or change library assets,
// shows each submitted asset in the 3D viewer straight from the pull request,
// and links to GitHub, where merging approves it and closing rejects it.
// Uses the public GitHub API without authentication (60 requests per hour).
import { openViewer } from "./viewer.js";

const CHECK_NAME = "Check asset submission";
const $ = (id) => document.getElementById(id);

async function getJson(url) {
  const response = await fetch(url, { headers: { Accept: "application/vnd.github+json" } });
  if (response.status === 403 && response.headers.get("x-ratelimit-remaining") === "0") {
    const reset = new Date(Number(response.headers.get("x-ratelimit-reset")) * 1000);
    throw new Error(`GitHub's limit for anonymous requests is used up until ${reset.toLocaleTimeString()}`);
  }
  if (!response.ok) throw new Error(`${url}: HTTP ${response.status}`);
  return response.json();
}

function badge(text, kind = "") {
  return Object.assign(document.createElement("span"), { className: `badge ${kind}`.trim(), textContent: text });
}

function checkBadge(check) {
  if (!check) return badge("check not run yet", "pending");
  if (check.status !== "completed") return badge("check running", "pending");
  return check.conclusion === "success" ? badge("check passed", "ok") : badge(`check ${check.conclusion}`, "fail");
}

async function loadSubmissions(repo, publishedIds) {
  const api = `https://api.github.com/repos/${repo}`;
  const pulls = await getJson(`${api}/pulls?state=open&per_page=50`);
  const submissions = [];
  for (const pr of pulls) {
    const files = await getJson(`${api}/pulls/${pr.number}/files?per_page=100`);
    const ids = [...new Set(files.map((f) => f.filename.match(/^library\/([^/]+)\//)?.[1]).filter(Boolean))];
    if (!ids.length) continue;
    const others = files.filter((f) => !/^(library|sources)\//.test(f.filename));
    let check = null;
    try {
      const runs = await getJson(`${api}/commits/${pr.head.sha}/check-runs?check_name=${encodeURIComponent(CHECK_NAME)}`);
      check = runs.check_runs[0] || null;
    } catch {
      check = null;
    }
    const raw = `https://raw.githubusercontent.com/${pr.head.repo.full_name}/${pr.head.sha}/`;
    for (const id of ids) {
      let meta = null;
      try {
        meta = await (await fetch(`${raw}library/${id}/meta.json`)).json();
      } catch {
        meta = null;
      }
      submissions.push({
        id, pr, check, meta, others,
        isUpdate: publishedIds.has(id),
        removed: files.some((f) => f.filename === `library/${id}/${id}.glb` && f.status === "removed"),
        glbUrl: `${raw}library/${id}/${id}.glb`,
        previewUrl: `${raw}library/${id}/preview.webp`,
      });
    }
  }
  return submissions;
}

function badgesFor(s) {
  const badges = [badge(`PR #${s.pr.number}`), badge(s.removed ? "removal" : s.isUpdate ? "update" : "new"), checkBadge(s.check)];
  if (s.others.length) badges.push(badge("also changes other files", "fail"));
  if (!s.meta) badges.push(badge("meta.json missing or invalid", "fail"));
  return badges;
}

function show(s) {
  history.replaceState(null, "", `#pr=${s.pr.number}&id=${s.id}`);
  const actions = [
    { label: "Approve or reject on GitHub", href: s.pr.html_url, primary: true },
    { label: "Changed files", href: `${s.pr.html_url}/files` },
  ];
  if (s.check?.html_url) actions.push({ label: "Check details", href: s.check.html_url });
  openViewer({
    name: s.meta?.name || s.id,
    description: s.meta?.description || "",
    tags: s.meta?.tags || [],
    glbUrl: s.glbUrl,
    badges: badgesFor(s),
    details: [
      ["Asset id", s.id],
      ["Author", s.meta?.author || "–"],
      ["Submitted by", `@${s.pr.user.login}`],
      ["Pull request", s.pr.title],
    ],
    actions,
    onClose: () => history.replaceState(null, "", location.pathname + location.search),
  });
}

function render(submissions) {
  const grid = $("grid");
  grid.replaceChildren();
  for (const s of submissions) {
    const card = Object.assign(document.createElement("button"), { type: "button", className: "card" });
    const img = Object.assign(document.createElement("img"), { src: s.previewUrl, alt: s.id, loading: "lazy" });
    const meta = Object.assign(document.createElement("div"), { className: "meta" });
    meta.append(
      Object.assign(document.createElement("div"), { className: "name", textContent: s.meta?.name || s.id }),
      Object.assign(document.createElement("div"), { className: "sub", textContent: `PR #${s.pr.number} by @${s.pr.user.login}` }),
    );
    const badges = Object.assign(document.createElement("div"), { className: "badges" });
    badges.append(...badgesFor(s).slice(1));
    meta.append(badges);
    card.append(img, meta);
    card.addEventListener("click", () => show(s));
    const item = document.createElement("li");
    item.append(card);
    grid.append(item);
  }
  $("status").textContent = submissions.length
    ? `${submissions.length} submission${submissions.length === 1 ? "" : "s"} waiting for review`
    : "No open submissions.";
}

try {
  const index = await (await fetch("library/index.json")).json();
  const repo = new URL(index.repository).pathname.replace(/^\/|\/$/g, "");
  $("pulls-link").href = `${index.repository}/pulls`;
  const submissions = await loadSubmissions(repo, new Set(index.assets.map((a) => a.id)));
  render(submissions);
  const params = new URLSearchParams(location.hash.slice(1));
  const linked = submissions.find((s) => String(s.pr.number) === params.get("pr") && (!params.get("id") || s.id === params.get("id")));
  if (linked) show(linked);
} catch (error) {
  $("status").textContent = `Could not load the submissions: ${error.message}`;
}
