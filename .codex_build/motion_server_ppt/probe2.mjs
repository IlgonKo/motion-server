import fs from "node:fs/promises";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";
const sourcePath = "C:/Users/Festo/Downloads/motion_server_overview (1).pptx";
const p = await PresentationFile.importPptx(await FileBlob.load(sourcePath));
console.log('count prop', p.slides.count);
console.log('items length', p.slides.items?.length);
for(let i=0;i<p.slides.count;i++){
 const s=p.slides.getItem(i);
 console.log(i, 'frame', JSON.stringify(s.frame), 'idx', s.index, 'num', s.slideNumber);
}
const snap = await p.inspect({kind:'slide,textbox,shape,image', maxChars:60000});
await fs.writeFile('.codex_build/motion_server_ppt/slide_inspect.ndjson', snap.ndjson);
console.log('wrote inspect');
