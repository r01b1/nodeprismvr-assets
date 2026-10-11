// Validate a .glb with the Khronos glTF-Validator; print the result as JSON.
// Usage: node validate_glb.mjs file.glb
import { readFileSync } from "node:fs";
import validator from "gltf-validator";

const report = await validator.validateBytes(new Uint8Array(readFileSync(process.argv[2])), {
  maxIssues: 50,
  externalResourceFunction: () => Promise.reject(new Error("external resources are not allowed")),
});
const { numErrors, numWarnings, numInfos, messages } = report.issues;
console.log(JSON.stringify({
  numErrors,
  numWarnings,
  numInfos,
  messages: messages.map((m) => ({ severity: m.severity, code: m.code, message: m.message, pointer: m.pointer })),
}));
