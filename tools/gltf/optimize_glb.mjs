#!/usr/bin/env node
// Compress a library GLB with glTF Transform and meshoptimizer.
//
//   node tools/gltf/optimize_glb.mjs IN.glb OUT.glb [--mode quantize|meshopt]
//        [--position-bits 14] [--normal-bits 8] [--color-bits 8]
//
// quantize (default): KHR_mesh_quantization stores positions, normals and
//   colours as 16- or 8-bit integers. three.js's GLTFLoader reads it as is.
// meshopt: EXT_meshopt_compression on top, a few times smaller again. Apps
//   must give their GLTFLoader three.js's MeshoptDecoder (setMeshoptDecoder).
//
// Both also drop unused and duplicate data and reorder vertices for the GPU.
// Run `npm ci --prefix tools/gltf` once.
import fs from "node:fs";
import { Logger, NodeIO } from "@gltf-transform/core";
import { ALL_EXTENSIONS } from "@gltf-transform/extensions";
import { dedup, meshopt, prune, quantize, reorder } from "@gltf-transform/functions";
import { MeshoptDecoder, MeshoptEncoder } from "meshoptimizer";

const args = process.argv.slice(2);
const option = (name, fallback) => {
  const i = args.indexOf(`--${name}`);
  if (i < 0) return fallback;
  const [value] = args.splice(i, 2).slice(1);
  return value;
};
const mode = option("mode", "quantize");
const bits = {
  quantizePosition: Number(option("position-bits", 14)),
  quantizeNormal: Number(option("normal-bits", 8)),
  quantizeColor: Number(option("color-bits", 8)),
};
const [input, output] = args;
if (!input || !output || !["quantize", "meshopt"].includes(mode)) {
  console.error("Usage: optimize_glb.mjs IN.glb OUT.glb [--mode quantize|meshopt] [--position-bits N] [--normal-bits N] [--color-bits N]");
  process.exit(2);
}

await Promise.all([MeshoptEncoder.ready, MeshoptDecoder.ready]);
const io = new NodeIO()
  .registerExtensions(ALL_EXTENSIONS)
  .registerDependencies({ "meshopt.decoder": MeshoptDecoder, "meshopt.encoder": MeshoptEncoder });
const document = await io.read(input);
document.setLogger(new Logger(Logger.Verbosity.WARN));
const steps = [dedup(), prune()];
if (mode === "meshopt") steps.push(meshopt({ encoder: MeshoptEncoder, level: "high", ...bits }));
else steps.push(reorder({ encoder: MeshoptEncoder }), quantize(bits));
await document.transform(...steps);
await io.write(output, document);

const kb = (path) => (fs.statSync(path).size / 1024).toFixed(1);
const used = document.getRoot().listExtensionsUsed().map((ext) => ext.extensionName);
console.log(JSON.stringify({ mode, ...bits, inputKB: Number(kb(input)), outputKB: Number(kb(output)), extensions: used }));
