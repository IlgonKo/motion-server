import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const workspaceDir = "C:/Users/Festo/Documents/motion-server";
const buildDir = path.join(workspaceDir, ".codex_build", "motion_server_ppt");
const finalPath = path.join(workspaceDir, ".codex_output", "motion_server_overview_customer_visual_v2.pptx");

const presentation = await PresentationFile.importPptx(await FileBlob.load(finalPath));
const montage = await presentation.export({ format: "webp", montage: true, scale: 1 });
await fs.writeFile(path.join(buildDir, "final_visual_v2_montage.webp"), new Uint8Array(await montage.arrayBuffer()));
for (let i = 0; i < presentation.slides.count; i++) {
  const slide = presentation.slides.getItem(i);
  const preview = await presentation.export({ slide, format: "png", scale: 1 });
  await fs.writeFile(path.join(buildDir, `final_visual_v2_slide_${i + 1}.png`), new Uint8Array(await preview.arrayBuffer()));
}

console.log(finalPath);
