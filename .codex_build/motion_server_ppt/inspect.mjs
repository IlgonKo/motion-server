import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";
const sourcePath = "C:/Users/Festo/Downloads/motion_server_overview (1).pptx";
const presentation = await PresentationFile.importPptx(await FileBlob.load(sourcePath));
const snapshot = await presentation.inspect({kind:"slide,textbox,shape,image,table,chart,notes,layout", maxChars:20000});
console.log(snapshot.ndjson);
console.error(JSON.stringify({slides:presentation.slides.length, size:presentation.slideSize}, null, 2));
