import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const workspaceDir = "C:/Users/Festo/Documents/motion-server";
const skillDir = "C:/Users/Festo/.codex/plugins/cache/openai-primary-runtime/presentations/26.905.11957/skills/presentations";
const runtimePython = "C:/Users/Festo/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe";
const buildDir = path.join(workspaceDir, ".codex_build", "motion_server_ppt");
const outDir = path.join(workspaceDir, ".codex_output");
const draftPath = path.join(buildDir, "motion_server_overview_customer_visual_v3_draft.pptx");
const finalPath = path.join(outDir, "motion_server_overview_customer_visual_v3.pptx");
const stagingDir = path.join(buildDir, "finalizer_visual_v3");

const { finalizePresentation } = await import(pathToFileURL(
  path.join(skillDir, "container_tools/artifact_tool_utils.mjs"),
).href);

await fs.mkdir(stagingDir, { recursive: true });
await fs.mkdir(outDir, { recursive: true });

const presentation = await PresentationFile.importPptx(await FileBlob.load(draftPath));
const candidatePath = path.join(stagingDir, "candidate.pptx");
await (await PresentationFile.exportPptx(presentation)).save(candidatePath);

const result = await finalizePresentation({
  explicitTotalSlideCount: 9,
  requiredNativeTableOwnerSlides: [],
  requiredNativeChartOwnerSlides: [],
  workspaceDir,
  candidatePath,
  finalPath,
  pythonExecutable: runtimePython,
  integrityValidatorPath: path.join(skillDir, "container_tools/inspect_presentation_package_integrity.py"),
  layoutValidatorPath: path.join(skillDir, "container_tools/inspect_presentation_layout_geometry.py"),
  layoutArgs: [
    "--expected-slide-size-emu",
    "12192000,6858000",
    "--validate-bullet-geometry",
    "--validate-heading-fit",
  ],
  fontPolicy: {
    basis: "design",
    families: ["Arial"],
  },
  verifyArtifactToolImport: true,
  receiptPath: path.join(stagingDir, "motion_server_overview_customer_visual_v3.validation.json"),
});

console.log(JSON.stringify(result, null, 2));
console.log(finalPath);
