import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const workspaceDir = "C:/Users/Festo/Documents/motion-server";
const sourcePath = "C:/Users/Festo/Downloads/motion_server_overview (1).pptx";
const buildDir = path.join(workspaceDir, ".codex_build", "motion_server_ppt");
const outDir = path.join(workspaceDir, ".codex_output");
await fs.mkdir(buildDir, { recursive: true });
await fs.mkdir(outDir, { recursive: true });

const p = await PresentationFile.importPptx(await FileBlob.load(sourcePath));

// Keep the Festo template slides 2-9 and remove the blank logo slide plus old deep-dive wrap-up slides.
while (p.slides.count > 9) p.slides.getItem(p.slides.count - 1).delete();
p.slides.getItem(0).delete();

const BLUE = "#0091CA";
const DARK = "#1F2933";
const MID = "#52616B";
const LIGHT = "#EAF6FB";
const GREEN = "#11A36A";
const ORANGE = "#F28C28";
const PURPLE = "#6E45E2";
const GRAY = "#F4F7F9";
const FONT = "Arial";

function clearSlide(slide) {
  slide.shapes.deleteAll();
  for (const image of [...slide.images.items]) slide.images.deleteById(image.id);
}

function addHeader(slide, title, slideNo) {
  slide.shapes.add({
    geometry: "rect",
    position: { left: 40, top: 138, width: 64, height: 4 },
    fill: BLUE,
    line: { fill: "none", width: 0 },
  });
  const t = slide.shapes.add({
    geometry: "textbox",
    position: { left: 40, top: 152, width: 840, height: 54 },
    fill: "none",
    line: { fill: "none", width: 0 },
  });
  t.text = title;
  t.text.style = { typeface: FONT, fontSize: 34, bold: true, color: DARK, autoFit: "shrinkText" };
  const f = slide.shapes.add({
    geometry: "textbox",
    position: { left: 58, top: 676, width: 680, height: 24 },
    fill: "none",
    line: { fill: "none", width: 0 },
  });
  f.text = "Motion Server overview";
  f.text.style = { typeface: FONT, fontSize: 10, color: MID };
  const n = slide.shapes.add({
    geometry: "textbox",
    position: { left: 1218, top: 676, width: 28, height: 22 },
    fill: "none",
    line: { fill: "none", width: 0 },
  });
  n.text = String(slideNo);
  n.text.style = { typeface: FONT, fontSize: 10, color: MID, alignment: "right" };
}

function addText(slide, text, pos, style = {}) {
  const s = slide.shapes.add({
    geometry: "textbox",
    position: pos,
    fill: "none",
    line: { fill: "none", width: 0 },
  });
  s.text = text;
  s.text.style = { typeface: FONT, fontSize: 22, color: DARK, autoFit: "shrinkText", ...style };
  return s;
}

function addBox(slide, text, pos, fill, style = {}) {
  const s = slide.shapes.add({
    geometry: "roundRect",
    position: pos,
    fill,
    line: { fill: "#D7E3EA", width: 1 },
  });
  s.text = text;
  s.text.style = { typeface: FONT, fontSize: 20, color: DARK, alignment: "center", verticalAlignment: "middle", autoFit: "shrinkText", ...style };
  return s;
}

function addKicker(slide, text, pos, color = BLUE) {
  const s = slide.shapes.add({ geometry: "textbox", position: pos, fill: "none", line: { fill: "none", width: 0 } });
  s.text = text;
  s.text.style = { typeface: FONT, fontSize: 15, bold: true, color, autoFit: "shrinkText" };
  return s;
}

function addBullets(slide, items, left, top, width, size = 22) {
  const lines = items.map(v => `• ${v}`).join("\n");
  return addText(slide, lines, { left, top, width, height: items.length * 46 + 20 }, { fontSize: size, color: DARK });
}

const slides = [];
for (let i = 0; i < p.slides.count; i++) {
  const slide = p.slides.getItem(i);
  clearSlide(slide);
  slide.background.fill = "#FFFFFF";
  slides.push(slide);
}

// 1 Cover
{
  const slide = slides[0];
  addText(slide, "MOTION SERVER", { left: 0, top: 170, width: 1280, height: 70 }, { fontSize: 44, bold: true, alignment: "center" });
  addText(slide, "쉽게 구성하는 모션 애플리케이션 플랫폼", { left: 0, top: 248, width: 1280, height: 42 }, { fontSize: 24, alignment: "center", color: MID });
  addBox(slide, "No dedicated controller\nNo complex motion code\nSame API for test and real devices", { left: 432, top: 350, width: 416, height: 132 }, LIGHT, { fontSize: 22, color: DARK });
  const footer = addText(slide, "Customer overview", { left: 0, top: 610, width: 1280, height: 30 }, { fontSize: 14, alignment: "center", color: MID });
}

// 2 Value
{
  const slide = slides[1];
  addHeader(slide, "Motion application development made simpler", 2);
  addText(slide, "Motion Server lets the application send simple commands while the server handles the device-specific details.", { left: 72, top: 218, width: 1080, height: 58 }, { fontSize: 24, color: MID });
  addBox(slide, "Application focuses on\nsequence and logic", { left: 90, top: 330, width: 300, height: 120 }, LIGHT, { fontSize: 21 });
  addBox(slide, "Motion Server handles\nmotion commands and units", { left: 490, top: 330, width: 300, height: 120 }, "#EAFBF3", { fontSize: 21 });
  addBox(slide, "Devices run through\none consistent API", { left: 890, top: 330, width: 300, height: 120 }, "#FFF4E8", { fontSize: 21 });
  addText(slide, "Result: faster prototyping, easier testing, and less custom integration work.", { left: 92, top: 535, width: 1040, height: 42 }, { fontSize: 25, bold: true, color: DARK });
}

// 3 What it does
{
  const slide = slides[2];
  addHeader(slide, "What Motion Server provides", 3);
  addBullets(slide, [
    "A TCP JSON command interface for motion, I/O, and device parameters",
    "Command authority so multiple clients do not send conflicting motion commands",
    "Automatic unit handling for linear and rotary axes",
    "Common feedback for panels, Node-RED flows, and other clients",
    "Fault and recovery commands for practical machine operation",
  ], 86, 230, 1040, 23);
}

// 4 Build flow
{
  const slide = slides[3];
  addHeader(slide, "From idea to motion sequence", 4);
  const xs = [78, 335, 592, 849];
  const labels = [
    ["Connect", "Open a TCP connection to Motion Server"],
    ["Request authority", "Reserve motion command control"],
    ["Send commands", "Enable, home, move, jog, or write I/O"],
    ["Watch feedback", "Use live status to continue the sequence"],
  ];
  labels.forEach(([a,b], i) => {
    addKicker(slide, `0${i+1}`, { left: xs[i], top: 260, width: 60, height: 24 }, BLUE);
    addBox(slide, `${a}\n${b}`, { left: xs[i], top: 292, width: 210, height: 145 }, i % 2 ? "#EAFBF3" : LIGHT, { fontSize: 19 });
    if (i < 3) addText(slide, "›", { left: xs[i] + 225, top: 334, width: 42, height: 55 }, { fontSize: 48, color: BLUE, alignment: "center" });
  });
  addText(slide, "The same command flow can run from a control panel, Node-RED, Python, or another host application.", { left: 90, top: 520, width: 1060, height: 54 }, { fontSize: 24, color: MID, alignment: "center" });
}

// 5 Low-code clients
{
  const slide = slides[4];
  addHeader(slide, "Low-code and reference clients", 5);
  addText(slide, "Motion Server is designed so customers can start without writing a full motion program from scratch.", { left: 72, top: 218, width: 1050, height: 60 }, { fontSize: 24, color: MID });
  addBox(slide, "Axis Control Panel\nManual operation and setup", { left: 86, top: 330, width: 315, height: 130 }, LIGHT, { fontSize: 21 });
  addBox(slide, "IO Control Panel\nI/O monitoring and parameter access", { left: 482, top: 330, width: 315, height: 130 }, "#EAFBF3", { fontSize: 21 });
  addBox(slide, "Node-RED flows\nBuild sequences visually", { left: 878, top: 330, width: 315, height: 130 }, "#F2EDFF", { fontSize: 21 });
  addText(slide, "Reference flows show how to combine motion, I/O, authority, and feedback in a simple application.", { left: 92, top: 540, width: 1040, height: 42 }, { fontSize: 23, bold: true, color: DARK });
}

// 6 Actual + virtual
{
  const slide = slides[5];
  addHeader(slide, "One API for real devices and virtual tests", 6);
  addText(slide, "The application can use the same Motion Server commands during simulation and on the real EtherCAT system.", { left: 72, top: 218, width: 1080, height: 60 }, { fontSize: 24, color: MID });
  addBox(slide, "Virtual devices\nTest sequence logic before hardware is ready", { left: 110, top: 330, width: 360, height: 145 }, "#F2EDFF", { fontSize: 21 });
  addBox(slide, "Motion Server API\nCommon commands and feedback", { left: 460, top: 352, width: 360, height: 100 }, LIGHT, { fontSize: 21, bold: true });
  addBox(slide, "Real devices\nRun the same application with EtherCAT hardware", { left: 810, top: 330, width: 360, height: 145 }, "#EAFBF3", { fontSize: 21 });
  addText(slide, "This supports early testing and a smoother move from virtual commissioning to real equipment.", { left: 100, top: 540, width: 1080, height: 42 }, { fontSize: 23, color: DARK, alignment: "center" });
}

// 7 Operation features
{
  const slide = slides[6];
  addHeader(slide, "Built-in controls for practical operation", 7);
  addBullets(slide, [
    "Command authority prevents conflicting motion commands from different clients",
    "Server feedback reports axis, I/O, authority, and diagnostic status",
    "Fault reset, bus reconnect, and server restart commands support recovery workflows",
    "Parameter access supports setup and troubleshooting from the same interface",
  ], 90, 235, 1040, 24);
  addBox(slide, "Customer applications stay simple because common operating tasks are already handled by Motion Server.", { left: 150, top: 540, width: 980, height: 70 }, "#FFF4E8", { fontSize: 23, bold: true });
}

// 8 Fit and next step
{
  const slide = slides[7];
  addHeader(slide, "Where Motion Server fits", 8);
  addText(slide, "Use Motion Server when a customer needs a fast path from manual testing to a working motion sequence.", { left: 72, top: 220, width: 1080, height: 60 }, { fontSize: 24, color: MID });
  addBox(slide, "Good fit\nSmall machines, lab systems, proof-of-concept stations, and customer demos", { left: 95, top: 330, width: 500, height: 150 }, "#EAFBF3", { fontSize: 22 });
  addBox(slide, "Next step\nConnect a device, open the panel, and build the first sequence with reference flows", { left: 685, top: 330, width: 500, height: 150 }, LIGHT, { fontSize: 22 });
  addText(slide, "Motion Server reduces the work needed to turn device control into an application.", { left: 120, top: 560, width: 1040, height: 48 }, { fontSize: 27, bold: true, alignment: "center", color: BLUE });
}

const draftPath = path.join(buildDir, "motion_server_overview_customer_draft.pptx");
await (await PresentationFile.exportPptx(p)).save(draftPath);
const montage = await p.export({ format: "webp", montage: true, scale: 1 });
await fs.writeFile(path.join(buildDir, "draft_montage.webp"), new Uint8Array(await montage.arrayBuffer()));
for (let i=0; i<p.slides.count; i++) {
  const slide = p.slides.getItem(i);
  const preview = await p.export({ slide, format: "png", scale: 1 });
  await fs.writeFile(path.join(buildDir, `draft_slide_${i+1}.png`), new Uint8Array(await preview.arrayBuffer()));
}
console.log(draftPath);
