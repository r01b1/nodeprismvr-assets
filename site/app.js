// Gallery of the NodePrism asset library.
// Reads the catalogue (library/index.json, built by tools/library/build_library_index.py,
// or what the page's library-catalog meta tag names); asset paths are relative to it.
import { catalogUrl, formatBytes, openViewer } from "./viewer.js";

const libraryUrl = new URL("./", catalogUrl);
const $ = (id) => document.getElementById(id);

let library = null;
const activeTags = new Set();

function assetUrl(asset, key) {
  return new URL(asset[key], libraryUrl).href;
}

function matches(asset, query) {
  const text = `${asset.name} ${asset.description} ${asset.category} ${asset.tags.join(" ")}`.toLowerCase();
  return query.split(/\s+/).every((word) => text.includes(word))
    && [...activeTags].every((tag) => asset.tags.includes(tag));
}

export function licenseLink(license, url) {
  if (!license) return "not set";
  if (!url) return license;
  const link = Object.assign(document.createElement("a"), { href: url, target: "_blank", rel: "noopener" });
  link.textContent = license;
  return link;
}

function renderTags() {
  const counts = new Map();
  for (const asset of library.assets) {
    for (const tag of asset.tags) counts.set(tag, (counts.get(tag) || 0) + 1);
  }
  const container = $("tags");
  container.replaceChildren();
  for (const [tag, count] of [...counts].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "tag";
    button.textContent = `${tag} (${count})`;
    button.setAttribute("aria-pressed", String(activeTags.has(tag)));
    button.addEventListener("click", () => {
      activeTags.has(tag) ? activeTags.delete(tag) : activeTags.add(tag);
      renderTags();
      renderGrid();
    });
    container.append(button);
  }
}

function renderGrid() {
  const query = $("search").value.trim().toLowerCase();
  const assets = library.assets.filter((asset) => matches(asset, query));
  const grid = $("grid");
  grid.replaceChildren();
  for (const asset of assets) {
    const item = document.createElement("li");
    const card = document.createElement("button");
    card.type = "button";
    card.className = "card";
    // Assets that exist only on a mirror may come without preview or stats.
    const img = document.createElement(asset.preview ? "img" : "div");
    if (asset.preview) {
      img.src = assetUrl(asset, "preview");
      img.alt = asset.name;
      img.loading = "lazy";
    } else {
      img.className = "no-preview";
      img.textContent = "No preview";
    }
    const meta = document.createElement("div");
    meta.className = "meta";
    const name = document.createElement("div");
    name.className = "name";
    name.textContent = asset.name;
    const sub = document.createElement("div");
    sub.className = "sub";
    sub.textContent = [
      asset.triangles != null ? `${asset.triangles.toLocaleString("en")} triangles` : asset.category,
      formatBytes(asset.bytes),
    ].join(" · ");
    meta.append(name, sub);
    card.append(img, meta);
    card.addEventListener("click", () => show(asset));
    item.append(card);
    grid.append(item);
  }
  const total = library.assets.length;
  $("status").textContent = assets.length === total
    ? `${total} asset${total === 1 ? "" : "s"}`
    : `${assets.length} of ${total} assets`;
}

function show(asset) {
  const glbUrl = assetUrl(asset, "file");
  const actions = [{ label: "Download .glb", href: glbUrl, primary: true, download: glbUrl.split("/").pop() }];
  if (asset.source) actions.push({ label: "Blender source", href: `${library.repository}/blob/main/${asset.source}` });
  history.replaceState(null, "", `#${asset.id}`);
  openViewer({
    name: asset.name,
    description: asset.description,
    tags: asset.tags,
    glbUrl,
    details: [
      ["Category", asset.category],
      ["License", licenseLink(asset.license, asset.license === library.license ? library.licenseUrl : null)],
      ["Author", asset.author || "–"],
      ["Added", asset.added],
    ],
    actions,
    showCode: true,
    onClose: () => history.replaceState(null, "", location.pathname + location.search),
  });
}

$("search").addEventListener("input", renderGrid);
$("catalog-link").href = catalogUrl.href;

try {
  // Pages lets browsers keep files for 10 minutes; revalidate the catalogue
  // so newly merged assets show up at once (an unchanged one costs a 304).
  const response = await fetch(catalogUrl, { cache: "no-cache" });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  library = await response.json();
  if (library.description) $("library-description").textContent = library.description;
  if (library.repository) $("repo-link").href = library.repository;
  if (library.license) $("footer-license").replaceChildren(licenseLink(library.license, library.licenseUrl));
  renderTags();
  renderGrid();
  const linked = library.assets.find((asset) => `#${asset.id}` === location.hash);
  if (linked) show(linked);
} catch (error) {
  $("status").textContent = `Could not load the library: ${error.message}`;
}
