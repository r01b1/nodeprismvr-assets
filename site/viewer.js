// 3D viewer dialog shared by the gallery and the review page.
// openViewer() shows a GLB with orbit controls and an info panel; triangle
// counts, size and materials are measured from the loaded model.
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";

const TEMPLATE = `
  <div class="viewer">
    <div class="stage">
      <canvas data-ref="canvas"></canvas>
      <p data-ref="status" class="viewer-status">Loading model…</p>
      <div class="toolbar">
        <button data-ref="wire" type="button" aria-pressed="false">Wireframe</button>
        <button data-ref="rotate" type="button" aria-pressed="true">Auto-rotate</button>
        <button data-ref="reset" type="button">Reset view</button>
      </div>
    </div>
    <aside class="info">
      <button data-ref="close" class="close" type="button" aria-label="Close">✕</button>
      <p data-ref="badges" class="badges"></p>
      <h2 data-ref="title"></h2>
      <p data-ref="description"></p>
      <dl data-ref="stats" class="stats"></dl>
      <div data-ref="tags" class="tags small"></div>
      <div data-ref="actions" class="actions"></div>
      <details data-ref="code" class="code">
        <summary>Use in three.js</summary>
        <pre><code data-ref="codeText"></code></pre>
      </details>
    </aside>
  </div>`;

let ui = null;
let renderer, scene, camera, controls, model, grid;
let wireframe = false;
let loadToken = 0;

export function formatBytes(bytes) {
  return bytes < 1024 * 1024 ? `${(bytes / 1024).toFixed(1)} KB` : `${(bytes / 1024 / 1024).toFixed(2)} MB`;
}

function element(tag, props = {}, children = []) {
  const node = Object.assign(document.createElement(tag), props);
  node.append(...children);
  return node;
}

function init() {
  const dialog = element("dialog", { className: "viewer-dialog" });
  dialog.setAttribute("aria-label", "3D viewer");
  dialog.innerHTML = TEMPLATE;
  document.body.append(dialog);
  ui = { dialog };
  for (const node of dialog.querySelectorAll("[data-ref]")) ui[node.dataset.ref] = node;

  renderer = new THREE.WebGLRenderer({ canvas: ui.canvas, antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x1a2028);
  scene.environment = new THREE.PMREMGenerator(renderer).fromScene(new RoomEnvironment(), 0.04).texture;
  camera = new THREE.PerspectiveCamera(40, 1, 0.01, 1000);
  controls = new OrbitControls(camera, ui.canvas);
  controls.enableDamping = true;
  controls.autoRotate = true;
  controls.autoRotateSpeed = 1.5;
  new ResizeObserver(resize).observe(ui.canvas.parentElement);

  ui.close.addEventListener("click", () => dialog.close());
  ui.wire.addEventListener("click", () => setWireframe(!wireframe));
  ui.rotate.addEventListener("click", () => {
    controls.autoRotate = !controls.autoRotate;
    ui.rotate.setAttribute("aria-pressed", String(controls.autoRotate));
  });
  ui.reset.addEventListener("click", () => model && frameModel());
  dialog.addEventListener("close", () => {
    renderer.setAnimationLoop(null);
    loadToken++;
    disposeModel();
    ui.onClose?.();
  });
}

function resize() {
  const { clientWidth: w, clientHeight: h } = ui.canvas.parentElement;
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
  ui.wire.setAttribute("aria-pressed", String(on));
  model?.traverse((node) => {
    if (node.isMesh) for (const material of [node.material].flat()) material.wireframe = on;
  });
}

function measure(root, bytes) {
  let triangles = 0;
  let vertices = 0;
  const materials = new Set();
  root.traverse((node) => {
    if (!node.isMesh) return;
    const geometry = node.geometry;
    const count = geometry.index ? geometry.index.count : geometry.attributes.position.count;
    triangles += Math.floor(count / 3);
    vertices += geometry.attributes.position.count;
    for (const material of [node.material].flat()) materials.add(material.name || "unnamed");
  });
  const size = new THREE.Box3().setFromObject(root).getSize(new THREE.Vector3());
  return [
    ["Triangles", triangles.toLocaleString("en")],
    ["Vertices", vertices.toLocaleString("en")],
    ["Size", `${size.x.toFixed(2)} × ${size.y.toFixed(2)} × ${size.z.toFixed(2)} m (x × y × z)`],
    ["File", formatBytes(bytes)],
    ["Materials", [...materials].join(", ")],
  ];
}

function renderStats(rows) {
  ui.stats.replaceChildren(...rows.flatMap(([key, value]) => [
    element("dt", { textContent: key }),
    element("dd", {}, [value]),
  ]));
}

/**
 * Show a GLB in the viewer dialog.
 * entry: { name, description, tags, glbUrl, details: [[label, text or Node]],
 *          badges: [Node], actions: [{ label, href, primary, download }],
 *          showCode, onClose }
 */
export async function openViewer(entry) {
  if (!ui) init();
  const token = ++loadToken;
  ui.onClose = entry.onClose;
  ui.title.textContent = entry.name;
  ui.description.textContent = entry.description || "";
  ui.badges.replaceChildren(...(entry.badges || []));
  ui.badges.hidden = !entry.badges?.length;
  renderStats(entry.details || []);
  ui.tags.replaceChildren(...(entry.tags || []).map((tag) => element("span", { className: "tag", textContent: tag })));
  ui.actions.replaceChildren(...(entry.actions || []).map((action) => {
    const link = element("a", { className: `button${action.primary ? " primary" : ""}`, href: action.href, textContent: action.label });
    if (action.download) link.setAttribute("download", action.download);
    else { link.target = "_blank"; link.rel = "noopener"; }
    return link;
  }));
  const copy = element("button", { className: "button", type: "button", textContent: "Copy URL" });
  copy.addEventListener("click", async () => {
    await navigator.clipboard.writeText(entry.glbUrl);
    copy.textContent = "Copied!";
  });
  ui.actions.append(copy);
  ui.code.hidden = !entry.showCode;
  ui.codeText.textContent =
    `import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";\n\n` +
    `new GLTFLoader().load(\n  "${entry.glbUrl}",\n  (gltf) => scene.add(gltf.scene),\n);`;

  if (!ui.dialog.open) ui.dialog.showModal();
  resize();
  disposeModel();
  ui.status.textContent = "Loading model…";
  ui.status.hidden = false;
  renderer.setAnimationLoop(() => {
    controls.update();
    renderer.render(scene, camera);
  });

  try {
    const response = await fetch(entry.glbUrl);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const buffer = await response.arrayBuffer();
    const gltf = await new GLTFLoader().parseAsync(buffer, entry.glbUrl.replace(/[^/]*$/, ""));
    if (token !== loadToken) return;  // another asset was opened meanwhile
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
    renderStats([...measure(model, buffer.byteLength), ...(entry.details || [])]);
    ui.status.hidden = true;
  } catch (error) {
    if (token === loadToken) ui.status.textContent = `Could not load the model: ${error.message || error}`;
  }
}
