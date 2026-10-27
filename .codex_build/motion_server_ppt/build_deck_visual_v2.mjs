import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const workspaceDir = "C:/Users/Festo/Documents/motion-server";
const sourcePath = "C:/Users/Festo/Downloads/motion_server_overview (1).pptx";
const buildDir = path.join(workspaceDir, ".codex_build", "motion_server_ppt");
const assetDir = path.join(buildDir, "assets");
const outDir = path.join(workspaceDir, ".codex_output");
await fs.mkdir(buildDir, { recursive: true });
await fs.mkdir(outDir, { recursive: true });

const p = await PresentationFile.importPptx(await FileBlob.load(sourcePath));
while (p.slides.count > 9) p.slides.getItem(p.slides.count - 1).delete();
p.slides.getItem(0).delete();

const BLUE = "#0091CA";
const BLUE2 = "#37B7E7";
const DARK = "#1F2933";
const MID = "#52616B";
const LIGHT = "#EAF6FB";
const GREEN = "#11A36A";
const GREEN_LIGHT = "#EAFBF3";
const ORANGE = "#F28C28";
const ORANGE_LIGHT = "#FFF4E8";
const PURPLE_LIGHT = "#F2EDFF";
const GRAY = "#F4F7F9";
const LINE = "#D7E3EA";
const FONT = "Arial";

const conceptBytes = await fs.readFile(path.join(assetDir, "motion_server_concept.png"));
const iconBytes = await fs.readFile(path.join(assetDir, "motion_server_icon.png"));

function clearSlide(slide) {
  slide.shapes.deleteAll();
  for (const image of [...slide.images.items]) slide.images.deleteById(image.id);
}

function addHeader(slide, title, slideNo) {
  slide.shapes.add({
    geometry: "rect",
    position: { left: 40, top: 118, width: 64, height: 4 },
    fill: BLUE,
    line: { fill: "none", width: 0 },
  });
  slide.shapes.add({
    geometry: "rect",
    position: { left: 40, top: 138, width: 40, height: 3 },
    fill: BLUE,
    line: { fill: "none", width: 0 },
  });
  addText(slide, title, { left: 50, top: 162, width: 780, height: 54 }, {
    fontSize: 34,
    bold: true,
  });
  addText(slide, "Motion Server overview", { left: 58, top: 676, width: 680, height: 24 }, {
    fontSize: 10,
    color: MID,
  });
  addText(slide, String(slideNo), { left: 1218, top: 676, width: 28, height: 22 }, {
    fontSize: 10,
    color: MID,
    alignment: "right",
  });
}

function addText(slide, text, pos, style = {}) {
  const s = slide.shapes.add({
    geometry: "textbox",
    position: pos,
    fill: "none",
    line: { fill: "none", width: 0 },
  });
  s.text = text;
  s.text.style = {
    typeface: FONT,
    fontSize: 22,
    color: DARK,
    autoFit: "shrinkText",
    ...style,
  };
  return s;
}

function addBox(slide, text, pos, fill, style = {}) {
  const s = slide.shapes.add({
    geometry: "roundRect",
    position: pos,
    fill,
    line: { fill: style.lineFill ?? LINE, width: style.lineWidth ?? 1 },
  });
  s.text = text;
  s.text.style = {
    typeface: FONT,
    fontSize: 20,
    color: DARK,
    alignment: "center",
    verticalAlignment: "middle",
    autoFit: "shrinkText",
    ...style,
  };
  return s;
}

function addPill(slide, text, left, top, width, fill = LIGHT, color = DARK) {
  return addBox(slide, text, { left, top, width, height: 36 }, fill, {
    fontSize: 16,
    bold: true,
    color,
    lineFill: fill,
  });
}

function addIconCircle(slide, icon, label, left, top, color = BLUE) {
  const c = slide.shapes.add({
    geometry: "ellipse",
    position: { left, top, width: 76, height: 76 },
    fill: color,
    line: { fill: "none", width: 0 },
  });
  c.text = icon;
  c.text.style = {
    typeface: FONT,
    fontSize: 31,
    color: "#FFFFFF",
    bold: true,
    alignment: "center",
    verticalAlignment: "middle",
  };
  addText(slide, label, { left: left - 34, top: top + 88, width: 144, height: 44 }, {
    fontSize: 17,
    bold: true,
    alignment: "center",
  });
}

function addArrow(slide, left, top, width, color = BLUE) {
  const s = slide.shapes.add({
    geometry: "rightArrow",
    position: { left, top, width, height: 32 },
    fill: color,
    line: { fill: "none", width: 0 },
  });
  return s;
}

function addImage(slide, bytes, pos, alt, fit = "cover") {
  slide.images.add({
    blob: bytes,
    contentType: "image/png",
    alt,
    fit,
    position: pos,
    geometry: "roundRect",
    borderRadius: "rounded-2xl",
  });
}

function addWindow(slide, left, top, width, height, title) {
  slide.shapes.add({
    geometry: "roundRect",
    position: { left, top, width, height },
    fill: "#FFFFFF",
    line: { fill: "#C9D8E0", width: 1 },
  });
  slide.shapes.add({
    geometry: "roundRect",
    position: { left: left + 10, top: top + 10, width: width - 20, height: 38 },
    fill: "#F7FAFC",
    line: { fill: "#E1E8EE", width: 1 },
  });
  addText(slide, title, { left: left + 24, top: top + 16, width: width - 180, height: 28 }, {
    fontSize: 18,
    bold: true,
  });
  return { left, top, width, height };
}

function addMiniButton(slide, label, left, top, width, fill = "#FFFFFF", color = DARK) {
  return addBox(slide, label, { left, top, width, height: 30 }, fill, {
    fontSize: 13,
    bold: true,
    color,
    lineFill: color === GREEN ? GREEN : LINE,
  });
}

function addLamp(slide, label, left, top, active = true) {
  slide.shapes.add({
    geometry: "ellipse",
    position: { left, top: top + 4, width: 15, height: 15 },
    fill: active ? GREEN : "#BAC6CE",
    line: { fill: "none", width: 0 },
  });
  addText(slide, label, { left: left + 22, top, width: 120, height: 24 }, {
    fontSize: 13,
    color: MID,
  });
}

function addChartMock(slide, left, top, width, height, color = BLUE) {
  slide.shapes.add({
    geometry: "rect",
    position: { left, top, width, height },
    fill: "#FFFFFF",
    line: { fill: LINE, width: 1 },
  });
  for (let i = 1; i < 4; i++) {
    slide.shapes.add({
      geometry: "rect",
      position: { left: left + 8, top: top + i * height / 4, width: width - 16, height: 1 },
      fill: "#EDF2F5",
      line: { fill: "none", width: 0 },
    });
  }
  const bars = [0.32, 0.48, 0.42, 0.66, 0.55, 0.82];
  const gap = 10;
  const barWidth = (width - 38 - gap * (bars.length - 1)) / bars.length;
  bars.forEach((value, i) => {
    const barHeight = (height - 30) * value;
    slide.shapes.add({
      geometry: "rect",
      position: {
        left: left + 18 + i * (barWidth + gap),
        top: top + height - 16 - barHeight,
        width: barWidth,
        height: barHeight,
      },
      fill: color,
      line: { fill: "none", width: 0 },
    });
  });
}

function addFlowNode(slide, label, left, top, fill = LIGHT, width = 150) {
  return addBox(slide, label, { left, top, width, height: 62 }, fill, {
    fontSize: 15,
    bold: true,
  });
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
  addText(slide, "MOTION SERVER", { left: 70, top: 146, width: 520, height: 70 }, {
    fontSize: 48,
    bold: true,
  });
  addText(slide, "복잡한 모션 제어를 간단한 앱으로", { left: 72, top: 224, width: 430, height: 46 }, {
    fontSize: 26,
    color: MID,
  });
  addPill(slide, "No dedicated controller", 76, 330, 230, LIGHT);
  addPill(slide, "Low-code sequence", 76, 380, 210, GREEN_LIGHT);
  addPill(slide, "Real and virtual devices", 76, 430, 240, PURPLE_LIGHT);
  addImage(slide, conceptBytes, { left: 510, top: 140, width: 690, height: 420 }, "Motion Server concept illustration", "cover");
  addText(slide, "Customer overview", { left: 76, top: 610, width: 360, height: 30 }, {
    fontSize: 14,
    color: MID,
  });
}

// 2 Customer value
{
  const slide = slides[1];
  addHeader(slide, "Customer value", 2);
  addText(slide, "Motion Server reduces custom control work between the application and the devices.", { left: 72, top: 225, width: 640, height: 60 }, {
    fontSize: 26,
    color: MID,
  });
  addIconCircle(slide, "PC", "PC application", 116, 350, BLUE);
  addArrow(slide, 242, 372, 90, BLUE2);
  addIconCircle(slide, "MS", "Motion Server", 358, 350, GREEN);
  addArrow(slide, 484, 372, 90, BLUE2);
  addIconCircle(slide, "AX", "Axis and I/O", 600, 350, ORANGE);
  addImage(slide, iconBytes, { left: 805, top: 215, width: 300, height: 300 }, "Motion Server device icon", "contain");
  addBox(slide, "Build the sequence.\nLet the server handle motion commands, feedback, and recovery.", { left: 760, top: 535, width: 410, height: 78 }, ORANGE_LIGHT, {
    fontSize: 20,
    bold: true,
  });
}

// 3 Axis operation screen
{
  const slide = slides[2];
  addHeader(slide, "Axis operation screen", 3);
  addWindow(slide, 90, 230, 1070, 365, "Axis Control Panel");
  addMiniButton(slide, "Request Authority", 295, 248, 126);
  addMiniButton(slide, "Bus Reconnect", 432, 248, 116);
  addMiniButton(slide, "Fault Reset", 560, 248, 94);
  addMiniButton(slide, "Disconnect", 1040, 248, 92, "#FFFFFF", GREEN);
  addText(slide, "Server: normal   Initialized: yes   Process data valid", { left: 116, top: 300, width: 740, height: 34 }, {
    fontSize: 18,
    color: MID,
  });
  addLamp(slide, "Authority available", 862, 302, true);
  addLamp(slide, "Connected", 1015, 302, true);
  const xs = [120, 320, 520, 720];
  xs.forEach((x, i) => {
    addBox(slide, `Axis ${i}\n${i === 1 ? "ready" : "normal"}`, { left: x, top: 350, width: 160, height: 74 }, i === 1 ? GREEN_LIGHT : LIGHT, {
      fontSize: 18,
      bold: true,
    });
  });
  addChartMock(slide, 920, 350, 190, 138, BLUE);
  addText(slide, "Position / velocity feedback", { left: 910, top: 500, width: 220, height: 28 }, {
    fontSize: 14,
    color: MID,
    alignment: "center",
  });
  addText(slide, "Manual setup and commissioning can start from a ready-made panel.", { left: 115, top: 535, width: 720, height: 34 }, {
    fontSize: 21,
    bold: true,
  });
}

// 4 Visual sequence flow
{
  const slide = slides[3];
  addHeader(slide, "Visual motion sequence", 4);
  addWindow(slide, 88, 240, 1090, 330, "Node-RED reference flow");
  const nodes = [
    ["Start", 130, 326, GREEN_LIGHT],
    ["Move axes\n0, 1", 315, 302, LIGHT],
    ["Move axes\n2, 3", 500, 302, LIGHT],
    ["Set output", 685, 302, ORANGE_LIGHT],
    ["Wait input", 860, 302, PURPLE_LIGHT, 150],
    ["Finish", 1030, 326, GREEN_LIGHT, 128],
  ];
  nodes.forEach(([label, x, y, fill, width]) => addFlowNode(slide, label, x, y, fill, width));
  [280, 465, 650, 835].forEach(x => addArrow(slide, x, 319, 44, BLUE2));
  addArrow(slide, 1010, 319, 30, BLUE2);
  addText(slide, "Prebuilt nodes make a sequence easy to assemble and modify.", { left: 115, top: 510, width: 830, height: 36 }, {
    fontSize: 23,
    bold: true,
  });
  addBox(slide, "No PLC-style motion code required", { left: 845, top: 500, width: 280, height: 54 }, LIGHT, {
    fontSize: 19,
    bold: true,
  });
}

// 5 I/O operation screen
{
  const slide = slides[4];
  addHeader(slide, "I/O operation screen", 5);
  addWindow(slide, 92, 232, 1070, 360, "IO Control Panel");
  addText(slide, "CPX-AP-I-EC   Modules: IOL, DI, DO, AI, AO", { left: 122, top: 294, width: 650, height: 30 }, {
    fontSize: 18,
    color: MID,
  });
  addBox(slide, "Digital input", { left: 120, top: 350, width: 180, height: 38 }, LIGHT, { fontSize: 16, bold: true });
  for (let i = 0; i < 8; i++) {
    slide.shapes.add({
      geometry: "ellipse",
      position: { left: 132 + i * 20, top: 405, width: 13, height: 13 },
      fill: i % 3 === 0 ? GREEN : "#BAC6CE",
      line: { fill: "none", width: 0 },
    });
  }
  addBox(slide, "Analog value", { left: 355, top: 350, width: 180, height: 38 }, GREEN_LIGHT, { fontSize: 16, bold: true });
  [0.55, 0.28, 0.74].forEach((v, i) => {
    slide.shapes.add({ geometry: "rect", position: { left: 375, top: 404 + i * 27, width: 130, height: 12 }, fill: "#E5EDF2", line: { fill: "none", width: 0 } });
    slide.shapes.add({ geometry: "rect", position: { left: 375, top: 404 + i * 27, width: 130 * v, height: 12 }, fill: BLUE, line: { fill: "none", width: 0 } });
  });
  addBox(slide, "IO-Link sensor", { left: 590, top: 350, width: 200, height: 38 }, PURPLE_LIGHT, { fontSize: 16, bold: true });
  addText(slide, "Profile 2\nVibration and temperature\nParameter read/write", { left: 608, top: 407, width: 170, height: 80 }, {
    fontSize: 16,
    alignment: "center",
  });
  addBox(slide, "Parameter storage", { left: 850, top: 350, width: 220, height: 38 }, ORANGE_LIGHT, { fontSize: 16, bold: true });
  addMiniButton(slide, "Volatile", 874, 414, 78);
  addMiniButton(slide, "Non-volatile", 964, 414, 100);
  addText(slide, "I/O status and parameter access use the same Motion Server connection.", { left: 125, top: 530, width: 900, height: 34 }, {
    fontSize: 22,
    bold: true,
  });
}

// 6 Same API
{
  const slide = slides[5];
  addHeader(slide, "Real devices and virtual tests", 6);
  addImage(slide, conceptBytes, { left: 120, top: 230, width: 1040, height: 330 }, "Application connected through Motion Server to real devices", "cover");
  addPill(slide, "Virtual device test", 150, 580, 190, PURPLE_LIGHT);
  addPill(slide, "Same command flow", 525, 580, 190, LIGHT);
  addPill(slide, "Real EtherCAT system", 895, 580, 210, GREEN_LIGHT);
}

// 7 Operating controls
{
  const slide = slides[6];
  addHeader(slide, "Operating controls", 7);
  const icons = [
    ["AUTH", "Command authority", 150, BLUE],
    ["FB", "Live feedback", 395, GREEN],
    ["RST", "Fault reset", 640, ORANGE],
    ["PAR", "Parameter access", 885, BLUE2],
  ];
  icons.forEach(([icon, label, x, color]) => addIconCircle(slide, icon, label, x, 265, color));
  addBox(slide, "Common tasks are available as ready-made commands, so the customer application can stay focused on sequence logic.", { left: 150, top: 465, width: 920, height: 86 }, ORANGE_LIGHT, {
    fontSize: 24,
    bold: true,
  });
  addText(slide, "Examples: enable, move, stop, fault reset, bus reconnect, I/O read/write", { left: 174, top: 575, width: 860, height: 34 }, {
    fontSize: 20,
    color: MID,
    alignment: "center",
  });
}

// 8 Fit and next step
{
  const slide = slides[7];
  addHeader(slide, "Best fit", 8);
  addBox(slide, "Customer demo\nShow motion quickly", { left: 110, top: 270, width: 280, height: 120 }, LIGHT, { fontSize: 22, bold: true });
  addBox(slide, "Lab system\nTest devices and sequences", { left: 500, top: 270, width: 280, height: 120 }, GREEN_LIGHT, { fontSize: 22, bold: true });
  addBox(slide, "Small machine\nBuild application logic first", { left: 890, top: 270, width: 280, height: 120 }, PURPLE_LIGHT, { fontSize: 22, bold: true });
  addArrow(slide, 404, 312, 70, BLUE2);
  addArrow(slide, 794, 312, 70, BLUE2);
  addBox(slide, "Next step: connect a device, open the panel, and build the first Node-RED sequence.", { left: 180, top: 500, width: 920, height: 80 }, ORANGE_LIGHT, {
    fontSize: 26,
    bold: true,
  });
}

const draftPath = path.join(buildDir, "motion_server_overview_customer_visual_v2_draft.pptx");
await (await PresentationFile.exportPptx(p)).save(draftPath);
const montage = await p.export({ format: "webp", montage: true, scale: 1 });
await fs.writeFile(path.join(buildDir, "visual_v2_montage.webp"), new Uint8Array(await montage.arrayBuffer()));
for (let i = 0; i < p.slides.count; i++) {
  const slide = p.slides.getItem(i);
  const preview = await p.export({ slide, format: "png", scale: 1 });
  await fs.writeFile(path.join(buildDir, `visual_v2_slide_${i + 1}.png`), new Uint8Array(await preview.arrayBuffer()));
}

console.log(draftPath);
