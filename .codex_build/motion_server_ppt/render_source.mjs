import fs from "node:fs/promises";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";
const sourcePath = "C:/Users/Festo/Downloads/motion_server_overview (1).pptx";
const p = await PresentationFile.importPptx(await FileBlob.load(sourcePath));
const montage = await p.export({format:'webp', montage:true, scale:1});
await fs.writeFile('.codex_build/motion_server_ppt/source_montage.webp', new Uint8Array(await montage.arrayBuffer()));
for (let i=0;i<p.slides.count;i++) {
 const slide=p.slides.getItem(i);
 const png=await p.export({slide, format:'png', scale:1});
 await fs.writeFile(`.codex_build/motion_server_ppt/source_slide_${i+1}.png`, new Uint8Array(await png.arrayBuffer()));
}
