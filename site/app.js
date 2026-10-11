// Gallery and 3D viewer for the NodePrism asset library.
// Reads library/index.json (built by tools/library/build_library_index.py).
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";

const libraryUrl = new URL("library/", location.href);
const $ = (id) => document.getElementById(id);

let library = null;
const activeTags = new Set();

function formatBytes(bytes) {
  return bytes < 1024 * 1024 ? `${(bytes / 1024).toFixed(1)} KB` : `${(bytes / 1024 / 1024).toFixed(2)} MB`;
}

function assetUrl(asset, key) {
  return new URL(asset[key], libraryUrl).href;
}

function matches(asset, query) {
  const text = `${asset.name} ${asset.description} ${asset.tags.join(" ")}`.toLowerCase();
  return query.split(/\s+/).every((word) => text.includes(word))
    && [...activeTags].every((tag) => asset.tags.includes(tag));
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
    const img = document.createElement("img");
    img.src = assetUrl(asset, "preview");
    img.alt = asset.name;
    img.loading = "lazy";
    const meta = document.createElement("div");
    meta.className = "meta";
    const name = document.createElement("div");
    name.className = "name";
    name.textContent = asset.name;
    const sub = document.createElement("div");
    sub.className = "sub";
    sub.textContent = `${asset.triangles.toLocaleString("en")} triangles · ${formatBytes(asset.bytes)}`;
    meta.append(name, sub);
    card.append(img, meta);
    card.addEventListener("click", () => openViewer(asset));
    item.append(card);
    grid.append(item);
  }
  const total = library.assets.length;
  $("status").textContent = assets.length === total
    ? `${total} asset${total === 1 ? "" : "s"}`
    : `${assets.length} of ${total} assets`;
}

// ---------------------------------------------------------------------------
// 3D viewer

let renderer, scene, camera, controls, model, grid;
let wireframe = false;
let frame = null;

function initViewer() {
  const canvas = $("canvas");
  renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x1a2028);
  scene.environment = new THREE.PMREMGenerator(renderer).fromScene(new RoomEnvironment(), 0.04).texture;
  camera = new THREE.PerspectiveCamera(40, 1, 0.01, 1000);
  controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true;
  controls.autoRotate = true;
  controls.autoRotateSpeed = 1.5;
  new ResizeObserver(resize).observe(canvas.parentElement);
}

function resize() {
  const { clientWidth: w, clientHeight: h } = $("canvas").parentElement;
  if (!w || !h) return;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}

function frameModel() {
  const box = new THREE.Box3().setFromObject(model);
  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());
  const radius = size.length() / 2 || 1;
  const distance = radius / Math.sin(THREE.MathUtils.degToRad(camera.fov / 2)) * 1.1;
  camera.position.copy(center).add(new THREE.Vector3(0.8, 0.5, 1).normalize().multiplyScalar(distance));
  camera.near = distance / 100;
  camera.far = distance * 100;
  camera.updateProjectionMatrix();
  controls.target.copy(center);
  controls.update();
}

function disposeModel() {
  if (!model) return;
  scene.remove(model);
  model.traverse((node) => {
    if (!node.isMesh) return;
    node.geometry.dispose();
    for (const material of [node.material].flat()) material.dispose();
  });
  model = null;
}

function setWireframe(on) {
  wireframe = on;
  $("btn-wire").setAttribute("aria-pressed", String(on));
  model?.traverse((node) => {
    if (node.isMesh) for (const material of [node.material].flat()) material.wireframe = on;
  });
}

function licenseLink(license) {
  if (!license) return "not set";
  if (!library.licenseUrl || license !== library.license) return license;
  const link = document.createElement("a");
  link.href = library.licenseUrl;
  link.target = "_blank";
  link.rel = "noopener";
  link.textContent = license;
  return link;
}

function fillInfo(asset) {
  const url = assetUrl(asset, "file");
  const repo = library.repository;
  const d = asset.dimensions;
  $("viewer-title").textContent = asset.name;
  $("viewer-description").textContent = asset.description;
  const rows = [
    ["Triangles", asset.triangles.toLocaleString("en")],
    ["Vertices", asset.vertices.toLocaleString("en")],
    ["Size", `${d.x.toFixed(2)} × ${d.y.toFixed(2)} × ${d.z.toFixed(2)} m (x × y × z)`],
    ["File", formatBytes(asset.bytes)],
    ["Materials", asset.materials.join(", ")],
    ["License", licenseLink(asset.license)],
    ["Author", asset.author],
    ["Added", asset.created],
  ];
  $("viewer-stats").replaceChildren(...rows.flatMap(([key, value]) => {
    const dt = document.createElement("dt");
    dt.textContent = key;
    const dd = document.createElement("dd");
    dd.append(value);
    return [dt, dd];
  }));
  $("viewer-tags").replaceChildren(...asset.tags.map((tag) => {
    const span = document.createElement("span");
    span.className = "tag";
    span.textContent = tag;
    return span;
  }));
  $("btn-download").href = url;
  $("btn-download").setAttribute("download", url.split("/").pop());
  $("btn-copy").textContent = "Copy URL";
  $("btn-copy").onclick = async () => {
    await navigator.clipboard.writeText(url);
    $("btn-copy").textContent = "Copied!";
  };
  $("btn-source").href = `${repo}/blob/main/${asset.source}`;
  $("viewer-code").textContent =
    `import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";\n\n` +
    `new GLTFLoader().load(\n  "${url}",\n  (gltf) => scene.add(gltf.scene),\n);`;
}

function openViewer(asset) {
  if (!renderer) initViewer();
  fillInfo(asset);
  history.replaceState(null, "", `#${asset.id}`);
  const dialog = $("viewer");
  if (!dialog.open) dialog.showModal();
  resize();
  disposeModel();
  $("viewer-status").textContent = "Loading model…";
  $("viewer-status").hidden = false;
  new GLTFLoader().load(assetUrl(asset, "file"), (gltf) => {
    disposeModel();
    model = gltf.scene;
    scene.add(model);
    const box = new THREE.Box3().setFromObject(model);
    const extent = Math.max(1, Math.ceil(Math.max(box.max.x - box.min.x, box.max.z - box.min.z) * 2));
    if (grid) scene.remove(grid);
    grid = new THREE.GridHelper(extent * 2, extent * 2, 0x3a4656, 0x2a3240);
    grid.position.y = box.min.y;
    scene.add(grid);
    setWireframe(wireframe);
    frameModel();
    $("viewer-status").hidden = true;
  }, undefined, (error) => {
    $("viewer-status").textContent = `Could not load the model: ${error.message || error}`;
  });
  if (!frame) {
    frame = () => {
      controls.update();
      renderer.render(scene, camera);
    };
    renderer.setAnimationLoop(frame);
  }
}

function closeViewer() {
  renderer?.setAnimationLoop(null);
  frame = null;
  disposeModel();
  history.replaceState(null, "", location.pathname + location.search);
}

$("btn-close").addEventListener("click", () => $("viewer").close());
$("viewer").addEventListener("close", closeViewer);
$("btn-wire").addEventListener("click", () => setWireframe(!wireframe));
$("btn-rotate").addEventListener("click", () => {
  controls.autoRotate = !controls.autoRotate;
  $("btn-rotate").setAttribute("aria-pressed", String(controls.autoRotate));
});
$("btn-reset").addEventListener("click", () => model && frameModel());
$("search").addEventListener("input", renderGrid);

// ---------------------------------------------------------------------------

try {
  const response = await fetch(new URL("index.json", libraryUrl));
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  library = await response.json();
  if (library.description) $("library-description").textContent = library.description;
  if (library.repository) $("repo-link").href = library.repository;
  if (library.license) $("footer-license").replaceChildren(licenseLink(library.license));
  renderTags();
  renderGrid();
  const linked = library.assets.find((asset) => `#${asset.id}` === location.hash);
  if (linked) openViewer(linked);
} catch (error) {
  $("status").textContent = `Could not load the library: ${error.message}`;
}
