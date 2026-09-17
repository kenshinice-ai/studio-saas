import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const __filename = fileURLToPath(import.meta.url);
const REPO_ROOT = path.resolve(path.dirname(__filename), "../..");
const SALES_DIR = path.join(REPO_ROOT, "docs", "sales");
const ASSET_DIR = path.join(SALES_DIR, "roadshow-assets");
// The .pptx goes to docs/sales/build/ (git-ignored), never onto the tracked
// deck. This generator is OLDER than docs/sales/PWE_Studio_Roadshow_Bilingual.pptx
// — see docs/sales/ROADSHOW_SOURCE.md — so writing there would replace the
// current deck with a previous one. Promoting a rebuild is a deliberate copy.
// The .html is this generator's own artefact and resolves roadshow-assets/
// relatively, so it stays beside them.
const BUILD_DIR = path.join(SALES_DIR, "build");
const PPTX_PATH = path.join(BUILD_DIR, "PWE_Studio_Roadshow_Bilingual.pptx");
const HTML_PATH = path.join(SALES_DIR, "PWE_Studio_Roadshow_Bilingual.html");
const PREVIEW_DIR = "/private/tmp/studiosaas-roadshow-20260809/preview";

const W = 1280;
const H = 720;
const GOLDEN_MAJOR = 0.618;
const ART_X = Math.round(W * GOLDEN_MAJOR);
const ART_W = W - ART_X;
const FONT_SANS = "Aptos";
const FONT_SERIF = "Georgia";
const COLORS = {
  navy: "#0E1729",
  navyRaised: "#16233D",
  navySoft: "#22355A",
  amber: "#F5B335",
  amberText: "#A16207",
  paper: "#F7F5F2",
  white: "#FFFFFF",
  ink: "#0E1729",
  slate: "#475569",
  muted: "#64748B",
  line: "#D9D5CE",
  warmPanel: "#EEE6DF",
  softGreen: "#E5F4EF",
  softAmber: "#FBF0D8",
  softBlue: "#E8F0FB",
  consoleBlue: "#2563EB",
  success: "#2F7951",
};

const ASSETS = {
  logoNavy: "pwe-logo-on-navy.png",
  logoPaper: "pwe-logo.png",
  markNavy: "pwe-mark-on-navy.png",
  markPaper: "pwe-mark.png",
  botanical: "botanical.png",
  coast: "coast.png",
  brandWorkbench: "brand-workbench.png",
  portal: "portal.png",
  quickRegistration: "quick-registration.png",
  pendingLeads: "pending-leads.png",
  classSchedule: "class-schedule.png",
  credits: "credits.png",
  activityLog: "activity-log.png",
  students: "students.png",
  works: "works.png",
  familyView: "family-view.png",
  businessStats: "business-stats.png",
};

const slides = [
  {
    number: 1,
    theme: "paper",
    titleEn: "Give the time back to the work.",
    titleZh: "把时间还给创作。",
    talk: "Open with the idea that the system should carry the operational weight while each studio keeps its own name, work and teaching style in front.",
    sources: [
      "README.md: product scope, public pilot and production status.",
      "docs/sales/talk_track.md: brand opening and core narrative.",
      "docs/design/Brand_Identity.md: Feather Star, product naming and colour system.",
      "Local visual asset: backend/frontend/assets/showcase-botanical-home.webp.",
    ],
  },
  {
    number: 2,
    theme: "paper",
    titleEn: "Your craft deserves more than admin.",
    titleZh: "你的才华，不该耗在行政里。",
    talk: "Name the operational friction before showing features: enquiries, schedules and credits are all necessary, but none of them is the reason a studio exists.",
    sources: [
      "docs/sales/talk_track.md: customer pain framing.",
      "README.md: studio owner outcome and product positioning.",
      "Local visual asset: backend/frontend/assets/showcase-coast-home.webp.",
    ],
  },
  {
    number: 3,
    theme: "paper",
    titleEn: "One studio brand. Four connected surfaces.",
    titleZh: "一个工作室品牌，四个协同表面。",
    talk: "Explain the surface model: Portal and Quick Registration face families; Studio Admin owns the public brand; CMS owns daily operations. They are separate by responsibility, connected by the same tenant.",
    sources: [
      "docs/Product_Surface_Model.md: canonical surface responsibilities and flows.",
      "README.md: Portal, CMS, Studio Admin and Register routes.",
      "Local visual assets: backend/frontend/assets/manual/01-brand-workbench.en.webp, 02-portal.en.webp, 02-register.en.webp, 03-roster.en.webp.",
    ],
  },
  {
    number: 4,
    theme: "paper",
    titleEn: "Your brand stays in front.",
    titleZh: "你的品牌始终在台前。",
    talk: "Show the brand workbench as the control point for a studio owner: logo, colours, bilingual copy, registration questions, preview and publish. The platform stays in the background.",
    sources: [
      "docs/Product_Surface_Model.md: Studio Admin owns brand and publication.",
      "docs/design/Brand_Identity.md: tenant identity precedence and sales-deck rules.",
      "Local visual asset: backend/frontend/assets/manual/01-brand-workbench.en.webp.",
    ],
  },
  {
    number: 5,
    theme: "paper",
    titleEn: "From first click to a reviewed lead.",
    titleZh: "从第一次点击，到一条可跟进的报名线索。",
    talk: "Walk left to right: a family discovers the studio, submits a focused registration, the team sees the pending record with its source and next action, then approves it into the studio workflow.",
    sources: [
      "docs/Product_Surface_Model.md: registration conversion flow.",
      "docs/customer/FAQ.md: registration, messaging and public-surface boundaries.",
      "Local visual assets: backend/frontend/assets/manual/02-register.en.webp and 02-pending.en.webp.",
    ],
  },
  {
    number: 6,
    theme: "paper",
    titleFontSize: 36,
    titleEn: "Give the teaching team a clearer day.",
    titleZh: "让团队把注意力放回课堂。",
    talk: "The value is not another dashboard. It is a calmer daily loop: see the class schedule, check attendance, notice low balances, post credits and leave an audit trail.",
    sources: [
      "docs/Product_Surface_Model.md: CMS owns schedules, attendance, credits and reporting.",
      "docs/customer/FAQ.md: privacy-safe ICS export and payment boundary.",
      "docs/HANDOFF_LATEST.md: current course-schedule release and browser acceptance.",
      "Local visual assets: backend/frontend/assets/manual/03-roster.en.webp, 04-topup.en.webp and 04-log.en.webp.",
    ],
  },
  {
    number: 7,
    theme: "paper",
    titleEn: "Families see progress, not administration.",
    titleZh: "家长看到的是成长，不是后台。",
    talk: "Move to the family perspective: the public portal can carry a curated studio showcase, while student access and portfolio stay private by default. This keeps the studio’s work visible without turning student records into a public feed.",
    sources: [
      "docs/design/Showcase_Section.md: studio-owned showcase is separate from the student work gallery and is curated in Studio Admin.",
      "docs/customer/Security_Privacy_Compliance.md: public portfolio sharing requires recorded consent and private media remains private by default.",
      "Local visual assets: backend/frontend/assets/manual/05-works.en.webp and 02-portal.en.webp.",
    ],
  },
  {
    number: 8,
    theme: "paper",
    titleEn: "Clarity is part of the product.",
    titleZh: "清晰的边界，也是产品的一部分。",
    talk: "Use trust as a product feature: tenant isolation, role-aware actions and privacy-aware media. Be explicit about what the current product does not claim, including online payments and automatic messaging.",
    sources: [
      "README.md: security baseline and explicit deferred boundaries.",
      "docs/customer/Security_Privacy_Compliance.md: tenant isolation, support access and consent chain.",
      "docs/customer/FAQ.md: no online payments, no automatic SMS/email and media privacy.",
      "VERSION: 9.8.3 in the current repository release marker; production record in README.md.",
      "Local visual asset: backend/frontend/assets/manual/04-log.en.webp.",
    ],
  },
  {
    number: 9,
    theme: "paper",
    titleEn: "Start focused. Grow with the studio.",
    titleZh: "先从清晰的范围开始，再随工作室成长。",
    talk: "Present the three subscription anchors, then qualify the scope: implementation, migration and training are quoted separately, and final price, GST and terms belong in the signed order form.",
    sources: [
      "backend/db/schema_v1.sql: current plan catalogue values.",
      "docs/customer/Pricing_and_Package_Boundaries.md: pricing, limits and commercial boundaries.",
      "README.md: SaaS and customer-owned Edition delivery models.",
    ],
  },
  {
    number: 10,
    theme: "paper",
    titleEn: "A 30-minute walkthrough, using your studio’s name.",
    titleZh: "用你的工作室名字，走一遍 30 分钟演示。",
    talk: "Close with a concrete next step: configure the studio identity, preview the public portal, walk through daily operations, and agree the onboarding path.",
    sources: [
      "docs/customer/Onboarding_Checklist.md: brand setup, migration, training and acceptance phases.",
      "docs/customer/Welcome_Pack.md: the four customer addresses and first steps.",
      "docs/sales/talk_track.md: closing CTA and demo discipline.",
      "Local visual asset: backend/frontend/assets/showcase-coast-home.webp.",
    ],
  },
];

const assetCache = new Map();

function assetPath(name) {
  return path.join(ASSET_DIR, name);
}

async function assetBytes(name) {
  if (!assetCache.has(name)) {
    assetCache.set(name, await fs.readFile(assetPath(name)));
  }
  return assetCache.get(name);
}

function addShape(slide, geometry, x, y, width, height, fill = "none", lineFill = "none", lineWidth = 0, options = {}) {
  return slide.shapes.add({
    geometry,
    name: options.name,
    position: { left: x, top: y, width, height },
    fill,
    line: { style: "solid", fill: lineFill, width: lineWidth },
    borderRadius: options.radius,
    shadow: options.shadow,
  });
}

function addText(slide, text, x, y, width, height, options = {}) {
  const shape = addShape(slide, "textbox", x, y, width, height, "none", "none", 0, { name: options.name });
  shape.text = text;
  shape.text.style = {
    fontSize: options.fontSize || 18,
    color: options.color || COLORS.ink,
    bold: options.bold || false,
    alignment: options.alignment || "left",
    verticalAlignment: options.verticalAlignment || "top",
    autoFit: options.autoFit || "shrinkText",
    wrap: "square",
    lineSpacing: options.lineSpacing || 1.05,
    insets: { top: 0, right: 0, bottom: 0, left: 0 },
    typeface: options.typeface || FONT_SANS,
  };
  return shape;
}

function addRule(slide, x, y, width, color, lineWidth = 1) {
  return addShape(slide, "line", x, y, width, 0, "none", color, lineWidth);
}

function addImage(slide, asset, x, y, width, height, options = {}) {
  return slide.images.add({
    blob: assetCache.get(asset),
    contentType: "image/png",
    alt: options.alt || asset,
    fit: options.fit || "cover",
    crop: options.crop,
    geometry: options.geometry || "roundRect",
    borderRadius: options.radius || 16,
    position: { left: x, top: y, width, height },
  });
}

function addImageFrame(slide, asset, x, y, width, height, options = {}) {
  addShape(slide, "roundRect", x, y, width, height, options.frameFill || COLORS.white, options.line || COLORS.line, 1, {
    radius: options.radius || 18,
    shadow: options.shadow === false ? undefined : "shadow-sm",
  });
  return addImage(slide, asset, x + 3, y + 3, width - 6, height - 6, {
    alt: options.alt || asset,
    fit: options.fit || "cover",
    crop: options.crop,
    radius: Math.max(8, (options.radius || 18) - 3),
  });
}

function addFooter(slide, number, theme) {
  addRule(slide, 72, 670, 1136, COLORS.line, 1);
  addText(slide, "PWE Studio  ·  Powered by Paradise Production · 天域文创", 72, 682, 700, 18, {
    fontSize: 11,
    color: COLORS.muted,
    typeface: FONT_SANS,
  });
  addText(slide, String(number).padStart(2, "0") + " / 10", 1110, 682, 98, 18, {
    fontSize: 11,
    color: COLORS.muted,
    alignment: "right",
    typeface: FONT_SANS,
  });
}

function addHeader(slide, titleEn, titleZh, theme, titleFontSize = 40) {
  addText(slide, "PWE STUDIO  ·  CUSTOMER ROADSHOW / 客户路演版", 72, 42, 620, 18, {
    fontSize: 11,
    bold: true,
    color: COLORS.amberText,
    typeface: FONT_SANS,
  });
  addText(slide, titleEn, 72, 72, 880, 54, {
    fontSize: titleFontSize,
    bold: true,
    color: COLORS.ink,
    typeface: FONT_SERIF,
    lineSpacing: .98,
  });
  addText(slide, titleZh, 72, 128, 900, 30, {
    fontSize: 22,
    color: COLORS.slate,
    typeface: "PingFang SC",
  });
}

function addBulletList(slide, items, x, y, width, height, theme, options = {}) {
  const paragraphs = items.map((item) => "•  " + item);
  return addText(slide, paragraphs.join("\n"), x, y, width, height, {
    fontSize: options.fontSize || 17,
    color: COLORS.ink,
    typeface: FONT_SANS,
    lineSpacing: options.lineSpacing || 1.25,
  });
}

function setNotes(slide, definition) {
  const sourceBlock = definition.sources.map((source) => "- " + source).join("\n");
  slide.speakerNotes.textFrame.setText(definition.talk + "\n\n[Sources]\n" + sourceBlock);
  slide.speakerNotes.setVisible(true);
}

function addPill(slide, text, x, y, width, theme, options = {}) {
  const fill = options.fill || COLORS.softBlue;
  const color = options.color || COLORS.ink;
  const border = options.border || COLORS.line;
  addShape(slide, "roundRect", x, y, width, options.height || 30, fill, border, 1, { radius: 15 });
  addText(slide, text, x + 12, y + 7, width - 24, 16, {
    fontSize: options.fontSize || 11,
    bold: true,
    color,
    alignment: "center",
    typeface: FONT_SANS,
  });
}

function addStep(slide, number, en, zh, x, y, width, theme, options = {}) {
  const fill = options.fill || COLORS.white;
  const line = options.line || COLORS.line;
  addShape(slide, "roundRect", x, y, width, options.height || 88, fill, line, 1, {
    radius: 16,
    shadow: options.shadow === false ? undefined : "shadow-sm",
  });
  addShape(slide, "ellipse", x + 16, y + 18, 36, 36, options.numberFill || COLORS.amber, "none", 0);
  addText(slide, String(number), x + 16, y + 26, 36, 18, {
    fontSize: 14,
    bold: true,
    color: COLORS.navy,
    alignment: "center",
    typeface: FONT_SANS,
  });
  addText(slide, en, x + 66, y + 17, width - 82, 24, {
    fontSize: 17,
    bold: true,
    color: COLORS.ink,
    typeface: FONT_SANS,
  });
  addText(slide, zh, x + 66, y + 46, width - 82, 22, {
    fontSize: 14,
    color: COLORS.slate,
    typeface: "PingFang SC",
  });
}

async function buildPptx() {
  const presentation = Presentation.create({ slideSize: { width: W, height: H } });

  for (const definition of slides) {
    const slide = presentation.slides.add();
    slide.background.fill = COLORS.paper;
    const theme = definition.theme;

    if (definition.number === 1) {
      addShape(slide, "rect", 0, 0, W, H, COLORS.paper);
      addImage(slide, ASSETS.botanical, ART_X, 0, ART_W, 720, {
        alt: "Watercolour botanical artwork",
        fit: "cover",
        geometry: "rect",
        radius: 0,
        crop: { left: 0.08, top: 0, right: 0.02, bottom: 0 },
      });
      addShape(slide, "rect", ART_X, 0, ART_W, 720, "#F7F5F2/18");
      addImage(slide, ASSETS.logoPaper, 72, 55, 180, 72, {
        alt: "PWE Studio",
        fit: "contain",
        geometry: "rect",
        radius: 0,
      });
      addText(slide, "PWE STUDIO  ·  CUSTOMER ROADSHOW / 客户路演版", 72, 173, 540, 18, {
        fontSize: 11,
        bold: true,
        color: COLORS.amberText,
      });
      addText(slide, definition.titleEn, 72, 220, 650, 86, {
        fontSize: 48,
        bold: true,
        color: COLORS.ink,
        typeface: FONT_SERIF,
        lineSpacing: .95,
      });
      addText(slide, definition.titleZh, 72, 317, 600, 42, {
        fontSize: 26,
        color: COLORS.slate,
        typeface: "PingFang SC",
      });
      addText(slide, "Studio management for art, music, dance and small education businesses.", 72, 400, 565, 52, {
        fontSize: 19,
        color: COLORS.slate,
        lineSpacing: 1.12,
      });
      addText(slide, "面向美术、音乐、舞蹈与小型教育机构的一体化运营系统。", 72, 461, 560, 34, {
        fontSize: 16,
        color: COLORS.ink,
        typeface: "PingFang SC",
      });
      addPill(slide, "PUBLIC PILOT / 公开试点", 72, 548, 164, "paper", { fill: COLORS.softAmber, border: COLORS.amber, color: COLORS.amberText });
      addPill(slide, "LIVE PRODUCTION / 已上线", 248, 548, 178, "paper", { fill: COLORS.softGreen, border: COLORS.success, color: COLORS.success });
      addPill(slide, "AUSTRALIA / 澳大利亚", 438, 548, 160, "paper", { fill: COLORS.softBlue, border: COLORS.line, color: COLORS.ink });
      addText(slide, "The system carries the operational weight. Your studio keeps the stage.", 72, 612, 650, 26, {
        fontSize: 14,
        color: COLORS.amberText,
        typeface: FONT_SANS,
      });
      addText(slide, "系统托住运营，工作室继续站在台前。", 72, 640, 520, 22, {
        fontSize: 13,
        color: COLORS.slate,
        typeface: "PingFang SC",
      });
      addFooter(slide, definition.number, theme);
      setNotes(slide, definition);
      continue;
    }

    if (definition.number !== 10) {
      addHeader(slide, definition.titleEn, definition.titleZh, theme, definition.titleFontSize || 40);
    }

    if (definition.number === 2) {
      addText(slide, "The work that steals a studio owner’s attention is rarely the teaching itself.", 72, 184, 770, 30, {
        fontSize: 19,
        color: COLORS.slate,
      });
      addText(slide, "真正消耗工作室主理人的，往往不是教学，而是教学之外的碎片。", 72, 218, 820, 24, {
        fontSize: 15,
        color: COLORS.muted,
        typeface: "PingFang SC",
      });
      const rows = [
        ["01", "Enquiries in chat", "询价散在聊天记录里", "follow-up gets fuzzy / 线索难跟进"],
        ["02", "Schedules in spreadsheets", "排课散在表格里", "changes are hard to share / 改动难同步"],
        ["03", "Credits by hand", "课时与出勤靠手工", "reconciliation waits until night / 晚上还要对账"],
      ];
      rows.forEach((row, index) => {
        const y = 295 + index * 104;
        addRule(slide, 72, y - 14, 1000, COLORS.line, 1);
        addText(slide, row[0], 72, y, 62, 32, { fontSize: 18, bold: true, color: COLORS.amberText });
        addText(slide, row[1], 158, y - 2, 340, 28, { fontSize: 22, bold: true, color: COLORS.ink });
        addText(slide, row[2], 158, y + 34, 340, 22, { fontSize: 15, color: COLORS.slate, typeface: "PingFang SC" });
        addText(slide, row[3], 630, y + 10, 430, 26, { fontSize: 17, color: COLORS.slate });
      });
      addShape(slide, "roundRect", 870, 548, 338, 92, COLORS.softAmber, COLORS.amber, 1, { radius: 18 });
      addText(slide, "Your attention is the scarce resource.", 896, 563, 230, 46, {
        fontSize: 18,
        bold: true,
        color: COLORS.ink,
        typeface: FONT_SERIF,
        lineSpacing: 1.08,
      });
      addText(slide, "真正稀缺的，是你的注意力。", 896, 611, 230, 18, {
        fontSize: 14,
        color: COLORS.amberText,
        typeface: "PingFang SC",
      });
      addImage(slide, ASSETS.markPaper, 1150, 561, 44, 44, { alt: "Feather Star mark", fit: "contain", geometry: "rect", radius: 0 });
      addFooter(slide, definition.number, theme);
    } else if (definition.number === 3) {
      addText(slide, "Public acquisition, brand publishing and daily operations stay separate — and connected.", 72, 184, 850, 30, {
        fontSize: 18,
        color: COLORS.slate,
      });
      addText(slide, "对外获客、品牌发布与日常运营彼此分工，也彼此相连。", 72, 218, 850, 24, {
        fontSize: 15,
        color: COLORS.muted,
        typeface: "PingFang SC",
      });
      const cards = [
        { asset: ASSETS.portal, x: 72, label: "Portal / 门户", desc: "Public studio site / 工作室官网" },
        { asset: ASSETS.quickRegistration, x: 352, label: "Quick Registration / 快速报名", desc: "QR-ready entry / 适合二维码" },
        { asset: ASSETS.brandWorkbench, x: 632, label: "Studio Admin / 品牌后台", desc: "Brand and publish / 品牌与发布" },
        { asset: ASSETS.classSchedule, x: 912, label: "CMS / 运营 CMS", desc: "Daily operations / 日常运营" },
      ];
      cards.forEach((card) => {
        addImageFrame(slide, card.asset, card.x, 280, 244, 178, { alt: card.label, radius: 16 });
        addText(slide, card.label, card.x, 474, 244, 24, { fontSize: 15, bold: true, color: COLORS.ink, alignment: "center" });
        addText(slide, card.desc, card.x, 502, 244, 20, { fontSize: 12, color: COLORS.slate, alignment: "center", typeface: card.label.includes("门") ? "PingFang SC" : FONT_SANS });
      });
      addShape(slide, "roundRect", 72, 562, 1084, 58, COLORS.softAmber, COLORS.amber, 1, { radius: 16 });
      addText(slide, "The platform stays behind the scenes; the studio name stays in front.", 96, 577, 770, 24, {
        fontSize: 17,
        color: COLORS.ink,
        typeface: FONT_SERIF,
      });
      addText(slide, "平台退到幕后，工作室名字站到台前。", 872, 578, 250, 20, {
        fontSize: 14,
        color: COLORS.amberText,
        alignment: "right",
        typeface: "PingFang SC",
      });
      addFooter(slide, definition.number, theme);
    } else if (definition.number === 4) {
      addImageFrame(slide, ASSETS.brandWorkbench, 72, 218, 690, 390, { alt: "Studio Admin brand workbench", radius: 20 });
      addPill(slide, "DRAFT → PREVIEW → PUBLISH", 72, 178, 196, "paper", { fill: COLORS.softBlue, border: COLORS.line, color: COLORS.ink });
      addText(slide, "Build the public experience in your own voice.", 814, 198, 360, 48, {
        fontSize: 25,
        bold: true,
        color: COLORS.ink,
        typeface: FONT_SERIF,
      });
      addText(slide, "用自己的语言，搭建对外的工作室体验。", 814, 256, 360, 26, {
        fontSize: 15,
        color: COLORS.amberText,
        typeface: "PingFang SC",
      });
      addBulletList(slide, [
        "Logo, colours and bilingual copy / Logo、配色与双语文案",
        "Registration fields and FAQs / 报名字段与常见问题",
        "Live preview before publishing / 发布前实时预览",
        "Tenant identity leads every customer surface / 每个客户表面都以你的身份为主",
      ], 814, 318, 370, 220, theme, { fontSize: 16, lineSpacing: 1.42 });
      addText(slide, "PWE Studio appears as the platform brand. Your studio appears as the experience.", 814, 570, 360, 44, {
        fontSize: 14,
        color: COLORS.slate,
        typeface: FONT_SANS,
      });
      addFooter(slide, definition.number, theme);
    } else if (definition.number === 5) {
      const stepX = [72, 315, 558, 801];
      const labels = [
        ["01", "Discover", "发现"],
        ["02", "Register", "报名"],
        ["03", "Review", "跟进"],
        ["04", "Convert", "建档"],
      ];
      labels.forEach((label, index) => {
        addStep(slide, label[0], label[1], label[2], stepX[index], 190, 210, theme, {
          fill: index === 3 ? COLORS.softAmber : COLORS.white,
          line: index === 3 ? COLORS.amber : COLORS.line,
          numberFill: index === 3 ? COLORS.amber : COLORS.softAmber,
        });
        if (index < labels.length - 1) {
          addShape(slide, "rightArrow", stepX[index] + 214, 223, 24, 24, COLORS.amber, "none", 0);
        }
      });
      addImageFrame(slide, ASSETS.quickRegistration, 72, 330, 534, 260, { alt: "Quick registration form", radius: 18 });
      addImageFrame(slide, ASSETS.pendingLeads, 674, 330, 534, 260, { alt: "Pending registration follow-up queue", radius: 18 });
      addText(slide, "A focused public entry.", 72, 602, 250, 20, { fontSize: 13, color: COLORS.slate });
      addText(slide, "一个聚焦的对外入口。", 335, 602, 250, 20, { fontSize: 13, color: COLORS.muted, typeface: "PingFang SC" });
      addText(slide, "A team-ready follow-up queue.", 674, 602, 260, 20, { fontSize: 13, color: COLORS.slate });
      addText(slide, "一条可执行的跟进队列。", 950, 602, 258, 20, { fontSize: 13, color: COLORS.muted, alignment: "right", typeface: "PingFang SC" });
      addFooter(slide, definition.number, theme);
    } else if (definition.number === 6) {
      addImageFrame(slide, ASSETS.classSchedule, 72, 218, 708, 390, { alt: "CMS class schedule", radius: 20 });
      addImageFrame(slide, ASSETS.credits, 824, 218, 384, 164, { alt: "Credits and settlement", radius: 16 });
      addImageFrame(slide, ASSETS.activityLog, 824, 406, 384, 202, { alt: "Activity log", radius: 16 });
      addPill(slide, "CLASS SCHEDULE / 课程安排", 72, 178, 180, "paper", { fill: COLORS.white, border: COLORS.line, color: COLORS.ink });
      addText(slide, "Plan · check in · track · export", 96, 630, 360, 20, { fontSize: 14, color: COLORS.slate });
      addText(slide, "排课 · 签到 · 课时 · 导出", 486, 630, 294, 20, { fontSize: 14, color: COLORS.muted, alignment: "right", typeface: "PingFang SC" });
      addFooter(slide, definition.number, theme);
    } else if (definition.number === 7) {
      addText(slide, "The public portal can curate studio work; student records remain private by default.", 72, 184, 900, 30, {
        fontSize: 18,
        color: COLORS.slate,
      });
      addText(slide, "官网可展示工作室精选作品；学员档案默认保持私密。", 72, 218, 820, 24, {
        fontSize: 15,
        color: COLORS.amberText,
        typeface: "PingFang SC",
      });
      addImageFrame(slide, ASSETS.works, 72, 286, 520, 306, { alt: "Studio work curation in CMS", radius: 18, frameFill: COLORS.white, line: COLORS.line });
      addImageFrame(slide, ASSETS.portal, 622, 286, 520, 306, { alt: "Selected work on the public studio portal", radius: 18, frameFill: COLORS.white, line: COLORS.line });
      addText(slide, "Curate selected work / 整理精选作品", 72, 610, 520, 24, { fontSize: 14, color: COLORS.ink, alignment: "center" });
      addText(slide, "Publish to the portal / 发布到工作室官网", 622, 610, 520, 24, { fontSize: 14, color: COLORS.ink, alignment: "center" });
      addFooter(slide, definition.number, theme);
    } else if (definition.number === 8) {
      addText(slide, "Trust is not a promise on the last slide. It is a boundary in every workflow.", 72, 184, 760, 30, {
        fontSize: 18,
        color: COLORS.slate,
      });
      addText(slide, "信任不是最后一页的口号，而是每条流程里的边界。", 72, 218, 760, 24, {
        fontSize: 15,
        color: COLORS.amberText,
        typeface: "PingFang SC",
      });
      const pillars = [
        ["Tenant isolation / 租户隔离", "Each studio’s data resolves through its own tenant context.\n数据按租户上下文解析。"],
        ["Role-based control / 角色权限", "Owner, manager, teacher and front desk do not see the same actions.\n不同角色看到不同操作。"],
        ["Privacy-aware media / 隐私保护", "Private by default; public portfolio sharing requires recorded consent.\n默认私密；公开作品需要有记录的同意。"],
      ];
      pillars.forEach((pillar, index) => {
        const y = 290 + index * 102;
        addShape(slide, "roundRect", 72, y, 604, 78, index === 1 ? COLORS.softAmber : COLORS.white, COLORS.line, 1, { radius: 16 });
        addShape(slide, "ellipse", 94, y + 22, 32, 32, COLORS.amber, "none", 0);
        addText(slide, String(index + 1), 94, y + 30, 32, 16, { fontSize: 13, bold: true, color: COLORS.navy, alignment: "center" });
        addText(slide, pillar[0], 148, y + 14, 496, 22, { fontSize: 16, bold: true, color: COLORS.ink });
        addText(slide, pillar[1], 148, y + 41, 496, 30, { fontSize: 12, color: COLORS.slate, lineSpacing: 1.18, typeface: FONT_SANS });
      });
      addImageFrame(slide, ASSETS.activityLog, 756, 254, 452, 348, { alt: "Audit activity log", radius: 18, frameFill: COLORS.white, line: COLORS.line });
      addPill(slide, "CURRENT PLATFORM · v9.8.3", 784, 622, 218, "paper", { fill: COLORS.amber, border: COLORS.amber, color: COLORS.ink, fontSize: 10 });
      addText(slide, "pwestudio.online · production", 1014, 630, 194, 18, { fontSize: 11, color: COLORS.slate, alignment: "right" });
      addFooter(slide, definition.number, theme);
    } else if (definition.number === 9) {
      addText(slide, "A transparent starting point. A scoped path to launch.", 72, 184, 760, 30, {
        fontSize: 18,
        color: COLORS.slate,
      });
      addText(slide, "清晰的订阅起点，配合按范围交付的上线路径。", 72, 218, 760, 24, {
        fontSize: 15,
        color: COLORS.muted,
        typeface: "PingFang SC",
      });
      const plans = [
        { x: 72, name: "Starter", zh: "起步", price: "$49", limit: "50 students · 1 seat · 15 works · 2 GB", limitZh: "50 名学员 · 1 席位 · 15 件作品 · 2 GB", fill: COLORS.white },
        { x: 448, name: "Studio", zh: "工作室", price: "$99", limit: "250 students · 5 seats · 60 works · 10 GB", limitZh: "250 名学员 · 5 席位 · 60 件作品 · 10 GB", fill: COLORS.softAmber, recommended: true },
        { x: 824, name: "Growth", zh: "成长", price: "$189", limit: "500 students · 20 seats · 150 works · 50 GB", limitZh: "500 名学员 · 20 席位 · 150 件作品 · 50 GB", fill: COLORS.white },
      ];
      plans.forEach((plan) => {
        const textColor = COLORS.ink;
        const subColor = plan.recommended ? COLORS.amberText : COLORS.slate;
        addShape(slide, "roundRect", plan.x, 288, 332, 238, plan.fill, plan.recommended ? COLORS.amber : COLORS.line, 1, { radius: 20, shadow: "shadow-sm" });
        if (plan.recommended) {
          addPill(slide, "RECOMMENDED / 推荐", plan.x + 20, 308, 176, "paper", { fill: COLORS.amber, border: COLORS.amber, color: COLORS.ink, fontSize: 10 });
        }
        addText(slide, plan.name, plan.x + 20, 354, 210, 28, { fontSize: 25, bold: true, color: textColor, typeface: FONT_SERIF });
        addText(slide, plan.zh, plan.x + 20, 386, 210, 20, { fontSize: 14, color: subColor, typeface: "PingFang SC" });
        addText(slide, plan.price, plan.x + 20, 430, 160, 44, { fontSize: 38, bold: true, color: textColor, typeface: FONT_SANS });
        addText(slide, "AUD / month", plan.x + 184, 451, 124, 20, { fontSize: 13, color: subColor, alignment: "right" });
        addRule(slide, plan.x + 20, 490, 292, plan.recommended ? COLORS.amber : COLORS.line, 1);
        addText(slide, plan.limit, plan.x + 20, 504, 292, 18, { fontSize: 13, color: textColor });
        addText(slide, plan.limitZh, plan.x + 20, 530, 292, 18, { fontSize: 12, color: subColor, typeface: "PingFang SC" });
      });
      addText(slide, "Implementation, migration and training are scoped separately. Final price, GST and terms are confirmed in the signed order form.", 72, 570, 1090, 24, {
        fontSize: 13,
        color: COLORS.slate,
      });
      addText(slide, "配置、迁移与培训按范围报价；最终价格、GST、期限与条款以签署的订单为准。", 72, 598, 1090, 22, {
        fontSize: 12,
        color: COLORS.muted,
        typeface: "PingFang SC",
      });
      addText(slide, "Available as multi-tenant SaaS or customer-owned Edition / 可选多租户 SaaS 或客户自有 Edition", 72, 633, 1090, 18, {
        fontSize: 11,
        color: COLORS.amberText,
      });
      addFooter(slide, definition.number, theme);
    } else if (definition.number === 10) {
      addImage(slide, ASSETS.coast, ART_X, 0, ART_W, 720, {
        alt: "Watercolour coastal artwork",
        fit: "cover",
        geometry: "rect",
        radius: 0,
        crop: { left: 0.04, top: 0, right: 0.06, bottom: 0 },
      });
      addShape(slide, "rect", ART_X, 0, ART_W, 720, "#F7F5F2/18");
      addImage(slide, ASSETS.logoPaper, 72, 55, 180, 72, { alt: "PWE Studio", fit: "contain", geometry: "rect", radius: 0 });
      addText(slide, "NEXT STEP / 下一步", 72, 184, 430, 20, { fontSize: 12, bold: true, color: COLORS.amberText });
      addText(slide, definition.titleEn, 72, 230, 640, 94, { fontSize: 44, bold: true, color: COLORS.ink, typeface: FONT_SERIF, lineSpacing: .98 });
      addText(slide, definition.titleZh, 72, 340, 620, 40, { fontSize: 24, color: COLORS.slate, typeface: "PingFang SC" });
      addText(slide, "Four steps. One working conversation.", 72, 419, 500, 24, { fontSize: 18, color: COLORS.slate });
      addText(slide, "四步走完一轮可执行的工作对话。", 72, 451, 500, 22, { fontSize: 15, color: COLORS.amberText, typeface: "PingFang SC" });
      const steps = [
        ["01", "Brand", "品牌"],
        ["02", "Portal", "门户"],
        ["03", "Operations", "运营"],
        ["04", "Launch path", "上线路径"],
      ];
      steps.forEach((step, index) => {
        const x = 72 + index * 146;
        addText(slide, step[0], x, 530, 40, 18, { fontSize: 12, bold: true, color: COLORS.amber });
        addText(slide, step[1], x, 553, 128, 22, { fontSize: 16, bold: true, color: COLORS.ink });
        addText(slide, step[2], x, 580, 128, 18, { fontSize: 13, color: COLORS.slate, typeface: "PingFang SC" });
      });
      addRule(slide, 72, 620, 624, COLORS.line, 1);
      addText(slide, "pwestudio.online", 72, 638, 300, 25, { fontSize: 18, bold: true, color: COLORS.amberText });
      addText(slide, "让系统退到幕后，把作品放回台前。", 394, 642, 302, 20, { fontSize: 14, color: COLORS.slate, typeface: "PingFang SC", alignment: "right" });
      addFooter(slide, definition.number, theme);
    }

    setNotes(slide, definition);
  }

  await fs.mkdir(PREVIEW_DIR, { recursive: true });
  await fs.mkdir(BUILD_DIR, { recursive: true });
  for (const [index, slide] of presentation.slides.items.entries()) {
    const png = await presentation.export({ slide, format: "png", scale: 1 });
    await fs.writeFile(path.join(PREVIEW_DIR, "slide-" + String(index + 1).padStart(2, "0") + ".png"), new Uint8Array(await png.arrayBuffer()));
    const layout = await slide.export({ format: "layout" });
    await fs.writeFile(path.join(PREVIEW_DIR, "slide-" + String(index + 1).padStart(2, "0") + ".layout.json"), await layout.text());
  }
  const montage = await presentation.export({ format: "webp", montage: true, scale: 1 });
  await fs.writeFile(path.join(PREVIEW_DIR, "deck-montage.webp"), new Uint8Array(await montage.arrayBuffer()));
  const inspect = await presentation.inspect({ kind: "slide,textbox,shape,image,notes", maxChars: 22000 });
  await fs.writeFile(path.join(PREVIEW_DIR, "inspect.ndjson"), inspect.ndjson);
  const pptx = await PresentationFile.exportPptx(presentation);
  await pptx.save(PPTX_PATH);
}

function esc(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function pos(x, y, width, height, extra = "") {
  return "left:" + x + "px;top:" + y + "px;width:" + width + "px;height:" + height + "px;" + extra;
}

function hDiv(cls, x, y, width, height, inner, extra = "") {
  return '<div class="' + cls + '" style="' + pos(x, y, width, height, extra) + '">' + inner + "</div>";
}

function hImg(asset, alt, x, y, width, height, extra = "") {
  return hDiv("image-frame", x, y, width, height, '<img src="roadshow-assets/' + esc(asset) + '" alt="' + esc(alt) + '">', extra);
}

function hText(cls, text, x, y, width, height, extra = "") {
  return hDiv(cls, x, y, width, height, esc(text), extra);
}

function hFooter(number, theme) {
  return hDiv("footer " + theme, 72, 670, 1136, 24,
    '<span>PWE Studio  ·  Powered by Paradise Production · 天域文创</span><span>' + String(number).padStart(2, "0") + " / 10</span>");
}

function hHeader(definition) {
  const titleExtra = definition.titleFontSize ? "font-size:" + definition.titleFontSize + "px;" : "";
  return hText("eyebrow", "PWE STUDIO  ·  CUSTOMER ROADSHOW / 客户路演版", 72, 42, 620, 18) +
    hText("title-en", definition.titleEn, 72, 72, 880, 56, titleExtra) +
    hText("title-zh", definition.titleZh, 72, 128, 900, 30);
}

function hPill(text, x, y, width, extra = "") {
  return hDiv("pill", x, y, width, 30, esc(text), extra);
}

function hStep(number, en, zh, x, y, width, extra = "", dark = false) {
  return hDiv("step" + (dark ? " dark" : ""), x, y, width, 88,
    '<span class="step-number">' + esc(number) + '</span><span class="step-en">' + esc(en) + '</span><span class="step-zh">' + esc(zh) + "</span>", extra);
}

function hFooterMeta() {
  return '<div class="nav-controls" aria-label="Slide navigation"><button class="nav-btn" data-action="prev" aria-label="Previous slide">←</button><span id="counter">1 / 10</span><button class="nav-btn" data-action="next" aria-label="Next slide">→</button></div><div class="progress-bar" id="progress"></div>';
}

function buildHtmlSlide(definition) {
  const n = definition.number;
  const theme = definition.theme;
  let content = "";
  if (n === 1) {
    content += hImg(ASSETS.botanical, "Watercolour botanical artwork", ART_X, 0, ART_W, 720, "border-radius:0;box-shadow:none;");
    content += hDiv("cover-image-scrim", ART_X, 0, ART_W, 720, "");
    content += hImg(ASSETS.logoPaper, "PWE Studio", 72, 55, 180, 72, "background:transparent;border:0;box-shadow:none;object-fit:contain;");
    content += hText("eyebrow cover", "PWE STUDIO  ·  CUSTOMER ROADSHOW / 客户路演版", 72, 173, 540, 18);
    content += hText("cover-title-en", definition.titleEn, 72, 220, 650, 86);
    content += hText("cover-title-zh", definition.titleZh, 72, 317, 600, 42);
    content += hText("cover-body-en", "Studio management for art, music, dance and small education businesses.", 72, 400, 565, 52);
    content += hText("cover-body-zh", "面向美术、音乐、舞蹈与小型教育机构的一体化运营系统。", 72, 461, 560, 34);
    content += hPill("PUBLIC PILOT / 公开试点", 72, 548, 164);
    content += hPill("LIVE PRODUCTION / 已上线", 248, 548, 178);
    content += hPill("AUSTRALIA / 澳大利亚", 438, 548, 160);
    content += hText("cover-note-en", "The system carries the operational weight. Your studio keeps the stage.", 72, 612, 650, 26);
    content += hText("cover-note-zh", "系统托住运营，工作室继续站在台前。", 72, 640, 520, 22);
    content += hFooter(n, theme);
  } else if (n === 2) {
    content += hHeader(definition);
    content += hText("lead-en", "The work that steals a studio owner’s attention is rarely the teaching itself.", 72, 184, 770, 30);
    content += hText("lead-zh", "真正消耗工作室主理人的，往往不是教学，而是教学之外的碎片。", 72, 218, 820, 24);
    const rows = [
      ["01", "Enquiries in chat", "询价散在聊天记录里", "follow-up gets fuzzy / 线索难跟进"],
      ["02", "Schedules in spreadsheets", "排课散在表格里", "changes are hard to share / 改动难同步"],
      ["03", "Credits by hand", "课时与出勤靠手工", "reconciliation waits until night / 晚上还要对账"],
    ];
    rows.forEach((row, index) => {
      const y = 295 + index * 104;
      content += '<div class="rule" style="' + pos(72, y - 14, 1000, 1) + '"></div>';
      content += hText("row-no", row[0], 72, y, 62, 32);
      content += hText("row-title", row[1], 158, y - 2, 340, 28);
      content += hText("row-zh", row[2], 158, y + 34, 340, 22);
      content += hText("row-detail", row[3], 630, y + 10, 430, 26);
    });
    content += hDiv("dark-callout", 870, 548, 338, 92, hText("callout-en", "Your attention is the scarce resource.", 26, 15, 230, 48) + hText("callout-zh", "真正稀缺的，是你的注意力。", 26, 60, 230, 20));
    content += hImg(ASSETS.markPaper, "Feather Star mark", 1150, 561, 44, 44, "background:transparent;border:0;box-shadow:none;object-fit:contain;");
    content += hFooter(n, theme);
  } else if (n === 3) {
    content += hHeader(definition);
    content += hText("lead-en", "Public acquisition, brand publishing and daily operations stay separate — and connected.", 72, 184, 850, 30);
    content += hText("lead-zh", "对外获客、品牌发布与日常运营彼此分工，也彼此相连。", 72, 218, 850, 24);
    const cards = [
      [ASSETS.portal, "Portal / 门户", "Public studio site / 工作室官网", 72],
      [ASSETS.quickRegistration, "Quick Registration / 快速报名", "QR-ready entry / 适合二维码", 352],
      [ASSETS.brandWorkbench, "Studio Admin / 品牌后台", "Brand and publish / 品牌与发布", 632],
      [ASSETS.classSchedule, "CMS / 运营 CMS", "Daily operations / 日常运营", 912],
    ];
    cards.forEach((card) => {
      content += hImg(card[0], card[1], card[3], 280, 244, 178);
      content += hText("card-label", card[1], card[3], 474, 244, 24);
      content += hText("card-desc", card[2], card[3], 502, 244, 20);
    });
    content += hDiv("navy-strip", 72, 562, 1084, 58, hText("strip-en", "The platform stays behind the scenes; the studio name stays in front.", 24, 15, 770, 24) + hText("strip-zh", "平台退到幕后，工作室名字站到台前。", 872, 16, 250, 20));
    content += hFooter(n, theme);
  } else if (n === 4) {
    content += hHeader(definition);
    content += hImg(ASSETS.brandWorkbench, "Studio Admin brand workbench", 72, 218, 690, 390);
    content += hPill("DRAFT → PREVIEW → PUBLISH", 72, 178, 196, "background:var(--color-soft-blue);color:var(--color-ink);border-color:var(--color-line);");
    content += hText("navy-side-title", "Build the public experience in your own voice.", 814, 198, 360, 48);
    content += hText("navy-side-zh", "用自己的语言，搭建对外的工作室体验。", 814, 256, 360, 26);
    content += hText("navy-bullets", "•  Logo, colours and bilingual copy / Logo、配色与双语文案\n•  Registration fields and FAQs / 报名字段与常见问题\n•  Live preview before publishing / 发布前实时预览\n•  Tenant identity leads every customer surface / 每个客户表面都以你的身份为主", 814, 318, 370, 220);
    content += hText("navy-small", "PWE Studio appears as the platform brand. Your studio appears as the experience.", 814, 570, 360, 44);
    content += hFooter(n, theme);
  } else if (n === 5) {
    content += hHeader(definition);
    const labels = [["01", "Discover", "发现"], ["02", "Register", "报名"], ["03", "Review", "跟进"], ["04", "Convert", "建档"]];
    [72, 315, 558, 801].forEach((x, index) => {
      content += hStep(labels[index][0], labels[index][1], labels[index][2], x, 190, 210, index === 3 ? "background:var(--color-soft-amber);border-color:var(--color-primary);" : "", false);
      if (index < 3) content += hDiv("arrow", x + 214, 223, 24, 24, "→");
    });
    content += hImg(ASSETS.quickRegistration, "Quick registration form", 72, 330, 534, 260);
    content += hImg(ASSETS.pendingLeads, "Pending registration follow-up queue", 674, 330, 534, 260);
    content += hText("caption-left-en", "A focused public entry.", 72, 602, 250, 20);
    content += hText("caption-left-zh", "一个聚焦的对外入口。", 335, 602, 250, 20);
    content += hText("caption-right-en", "A team-ready follow-up queue.", 674, 602, 260, 20);
    content += hText("caption-right-zh", "一条可执行的跟进队列。", 950, 602, 258, 20);
    content += hFooter(n, theme);
  } else if (n === 6) {
    content += hHeader(definition);
    content += hImg(ASSETS.classSchedule, "CMS class schedule", 72, 218, 708, 390);
    content += hImg(ASSETS.credits, "Credits and settlement", 824, 218, 384, 164);
    content += hImg(ASSETS.activityLog, "Activity log", 824, 406, 384, 202);
    content += hPill("CLASS SCHEDULE / 课程安排", 72, 178, 180, "background:var(--color-white);color:var(--color-ink);border-color:var(--color-line);");
    content += hText("caption-left-en", "Plan · check in · track · export", 96, 630, 360, 20);
    content += hText("caption-left-zh", "排课 · 签到 · 课时 · 导出", 486, 630, 294, 20);
    content += hFooter(n, theme);
  } else if (n === 7) {
    content += hHeader(definition);
    content += hText("navy-lead-en", "The public portal can curate studio work; student records remain private by default.", 72, 184, 900, 30);
    content += hText("navy-lead-zh", "官网可展示工作室精选作品；学员档案默认保持私密。", 72, 218, 820, 24);
    content += hImg(ASSETS.works, "Studio work curation in CMS", 72, 286, 520, 306);
    content += hImg(ASSETS.portal, "Selected work on the public studio portal", 622, 286, 520, 306);
    content += hText("navy-caption", "Curate selected work / 整理精选作品", 72, 610, 520, 24);
    content += hText("navy-caption", "Publish to the portal / 发布到工作室官网", 622, 610, 520, 24);
    content += hFooter(n, theme);
  } else if (n === 8) {
    content += hHeader(definition);
    content += hText("navy-lead-en", "Trust is not a promise on the last slide. It is a boundary in every workflow.", 72, 184, 760, 30);
    content += hText("navy-lead-zh", "信任不是最后一页的口号，而是每条流程里的边界。", 72, 218, 760, 24);
    const pillars = [
      ["Tenant isolation / 租户隔离", "Each studio’s data resolves through its own tenant context.\n数据按租户上下文解析。"],
      ["Role-based control / 角色权限", "Owner, manager, teacher and front desk do not see the same actions.\n不同角色看到不同操作。"],
      ["Privacy-aware media / 隐私保护", "Private by default; public portfolio sharing requires recorded consent.\n默认私密；公开作品需要有记录的同意。"],
    ];
    pillars.forEach((pillar, index) => {
      const y = 290 + index * 102;
      content += hDiv("trust-pillar", 72, y, 604, 78, '<span class="trust-number">' + (index + 1) + "</span>" + hText("trust-title", pillar[0], 76, 14, 496, 22) + hText("trust-copy", pillar[1], 76, 41, 496, 30));
    });
    content += hImg(ASSETS.activityLog, "Audit activity log", 756, 254, 452, 348, "background:var(--color-background-raised);border-color:var(--color-background-soft);");
    content += hPill("CURRENT PLATFORM · v9.8.3", 784, 622, 218, "background:var(--color-primary);color:var(--color-primary-text);border-color:var(--color-primary);");
    content += hText("health-date", "pwestudio.online · production", 1014, 630, 194, 18);
    content += hFooter(n, theme);
  } else if (n === 9) {
    content += hHeader(definition);
    content += hText("lead-en", "A transparent starting point. A scoped path to launch.", 72, 184, 760, 30);
    content += hText("lead-zh", "清晰的订阅起点，配合按范围交付的上线路径。", 72, 218, 760, 24);
    const plans = [
      ["Starter", "起步", "$49", "50 students · 1 seat · 15 works · 2 GB", "50 名学员 · 1 席位 · 15 件作品 · 2 GB", 72, ""],
      ["Studio", "工作室", "$99", "250 students · 5 seats · 60 works · 10 GB", "250 名学员 · 5 席位 · 60 件作品 · 10 GB", 448, "recommended"],
      ["Growth", "成长", "$189", "500 students · 20 seats · 150 works · 50 GB", "500 名学员 · 20 席位 · 150 件作品 · 50 GB", 824, ""],
    ];
    plans.forEach((plan) => {
      content += hDiv("plan " + plan[6], plan[5], 288, 332, 238,
        (plan[6] ? hPill("RECOMMENDED / 推荐", 20, 20, 176) : "") +
        hText("plan-name", plan[0], 20, 66, 210, 28) +
        hText("plan-zh", plan[1], 20, 98, 210, 20) +
        hText("plan-price", plan[2], 20, 142, 160, 44) +
        hText("plan-currency", "AUD / month", 184, 163, 124, 20) +
        '<div class="plan-rule" style="' + pos(20, 202, 292, 1) + '"></div>' +
        hText("plan-limit", plan[3], 20, 216, 292, 18) +
        hText("plan-limit-zh", plan[4], 20, 242, 292, 18));
    });
    content += hText("pricing-note", "Implementation, migration and training are scoped separately. Final price, GST and terms are confirmed in the signed order form.", 72, 570, 1090, 24);
    content += hText("pricing-note-zh", "配置、迁移与培训按范围报价；最终价格、GST、期限与条款以签署的订单为准。", 72, 598, 1090, 22);
    content += hText("edition-note", "Available as multi-tenant SaaS or customer-owned Edition / 可选多租户 SaaS 或客户自有 Edition", 72, 633, 1090, 18);
    content += hFooter(n, theme);
  } else if (n === 10) {
    content += hImg(ASSETS.coast, "Watercolour coastal artwork", ART_X, 0, ART_W, 720, "border-radius:0;box-shadow:none;");
    content += hDiv("cover-image-scrim", ART_X, 0, ART_W, 720, "");
    content += hImg(ASSETS.logoPaper, "PWE Studio", 72, 55, 180, 72, "background:transparent;border:0;box-shadow:none;object-fit:contain;");
    content += hText("eyebrow cover", "NEXT STEP / 下一步", 72, 184, 430, 20);
    content += hText("cover-title-en", definition.titleEn, 72, 230, 640, 94);
    content += hText("cover-title-zh", definition.titleZh, 72, 340, 620, 40);
    content += hText("cover-body-en", "Four steps. One working conversation.", 72, 419, 500, 24);
    content += hText("cover-body-zh", "四步走完一轮可执行的工作对话。", 72, 451, 500, 22);
    const steps = [["01", "Brand", "品牌"], ["02", "Portal", "门户"], ["03", "Operations", "运营"], ["04", "Launch path", "上线路径"]];
    steps.forEach((step, index) => {
      const x = 72 + index * 146;
      content += hText("step-no", step[0], x, 530, 40, 18);
      content += hText("step-label", step[1], x, 553, 128, 22);
      content += hText("step-zh", step[2], x, 580, 128, 18);
    });
    content += '<div class="rule dark" style="' + pos(72, 620, 624, 1) + '"></div>';
    content += hText("cta-url", "pwestudio.online", 72, 638, 300, 25);
    content += hText("cta-zh", "让系统退到幕后，把作品放回台前。", 394, 642, 302, 20);
    content += hFooter(n, theme);
  }
  return '<section class="slide theme-' + theme + '" data-slide="' + n + '">' + content + "</section>";
}

const HTML_CSS = [
  "* { box-sizing: border-box; }",
  "html, body { margin: 0; width: 100%; height: 100%; overflow: hidden; background: var(--color-background); }",
  "body { color: var(--slide-ink); font-family: var(--typography-font-body); -webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility; }",
  ".slide-deck { position: relative; width: 100vw; height: 100vh; overflow: hidden; }",
  ".slide { position: absolute; inset: 0; width: 100%; height: 100%; padding: 0; opacity: 0; visibility: hidden; transition: opacity .233s ease; overflow: hidden; }",
  ".slide.active { opacity: 1; visibility: visible; }",
  ".theme-paper { background: var(--color-paper); color: var(--color-ink); }",
  ".theme-navy { background: var(--color-paper); color: var(--color-ink); }",
  ".slide > div { position: absolute; }",
  ".eyebrow { color: var(--color-amber-text); font-size: 11px; font-weight: 700; letter-spacing: .12em; line-height: 18px; }",
  ".theme-navy .eyebrow { color: var(--color-amber-text); }",
  ".title-en, .cover-title-en { font-family: var(--typography-font-heading); font-size: 40px; line-height: .98; font-weight: 700; letter-spacing: -.02em; white-space: nowrap; }",
  ".title-zh, .cover-title-zh { font-family: var(--typography-font-heading); font-size: 22px; line-height: 30px; }",
  ".theme-paper .title-zh { color: var(--color-ink-soft); }",
  ".theme-navy .title-zh { color: var(--color-ink-soft); }",
  ".lead-en, .row-detail, .caption-left-en, .caption-right-en { color: var(--color-ink-soft); font-size: 18px; line-height: 30px; }",
  ".lead-zh, .row-zh, .caption-left-zh, .caption-right-zh { color: var(--color-muted); font-size: 15px; line-height: 24px; font-family: \"PingFang SC\", var(--typography-font-body); }",
  ".row-no { color: var(--color-amber-text); font-size: 18px; font-weight: 700; }",
  ".row-title { color: var(--color-ink); font-size: 22px; font-weight: 700; }",
  ".rule { background: var(--color-line); }",
  ".rule.dark { background: var(--color-line); }",
  ".image-frame { overflow: hidden; border: 1px solid var(--color-line); border-radius: var(--slide-radius); background: var(--color-white); box-shadow: var(--slide-shadow); }",
  ".image-frame img { width: 100%; height: 100%; display: block; object-fit: cover; }",
  ".theme-navy .image-frame { border-color: var(--color-line); background: var(--color-white); }",
  ".cover-image-scrim { background: color-mix(in srgb, var(--color-paper) 16%, transparent); pointer-events: none; }",
  ".cover-title-en { color: var(--color-ink); font-size: 48px; line-height: .95; }",
  ".cover-title-zh { color: var(--color-ink-soft); font-size: 26px; }",
  ".cover-body-en { color: var(--color-ink-soft); font-size: 19px; line-height: 1.12; }",
  ".cover-body-zh { color: var(--color-ink); font-family: \"PingFang SC\", var(--typography-font-body); font-size: 16px; }",
  ".cover-note-en { color: var(--color-amber-text); font-size: 14px; }",
  ".cover-note-zh { color: var(--color-ink-soft); font-family: \"PingFang SC\", var(--typography-font-body); font-size: 13px; }",
  ".pill { display: flex; align-items: center; justify-content: center; padding: 0 12px; border: 1px solid var(--color-line); border-radius: 999px; background: var(--color-soft-blue); color: var(--color-ink); font-size: 11px; font-weight: 700; letter-spacing: .02em; white-space: nowrap; }",
  ".theme-paper .pill { background: var(--color-soft-blue); border-color: var(--color-line); color: var(--color-ink); }",
  ".dark-callout { border: 1px solid var(--color-primary); border-radius: 18px; background: var(--color-soft-amber); color: var(--color-ink); }",
  ".dark-callout > div, .navy-strip > div, .trust-pillar > div, .plan > div { position: absolute; }",
  ".callout-en { color: var(--color-ink); font-family: var(--typography-font-heading); font-size: 18px; line-height: 24px; }",
  ".callout-zh { color: var(--color-amber-text); font-family: \"PingFang SC\", var(--typography-font-body); font-size: 14px; }",
  ".card-label { color: var(--color-ink); font-size: 15px; font-weight: 700; text-align: center; }",
  ".card-desc { color: var(--color-ink-soft); font-size: 12px; text-align: center; }",
  ".navy-strip { border: 1px solid var(--color-primary); border-radius: 16px; background: var(--color-soft-amber); color: var(--color-ink); }",
  ".strip-en { color: var(--color-ink); font-family: var(--typography-font-heading); font-size: 17px; }",
  ".strip-zh { color: var(--color-amber-text); font-family: \"PingFang SC\", var(--typography-font-body); font-size: 14px; text-align: right; }",
  ".navy-side-title { color: var(--color-ink); font-family: var(--typography-font-heading); font-size: 25px; line-height: 1.05; font-weight: 700; }",
  ".navy-side-zh { color: var(--color-amber-text); font-family: \"PingFang SC\", var(--typography-font-body); font-size: 15px; }",
  ".navy-bullets, .navy-small { color: var(--color-ink); font-size: 16px; line-height: 1.42; white-space: pre-line; }",
  ".arrow { display: flex; align-items: center; justify-content: center; color: var(--color-amber-text); font-size: 22px; font-weight: 700; }",
  ".step { border: 1px solid var(--color-line); border-radius: 16px; background: var(--color-white); padding: 17px 12px 12px 66px; }",
  ".theme-paper .step .step-en { color: var(--color-ink); }",
  ".step-number { position: absolute; left: 16px; top: 18px; width: 36px; height: 36px; display: flex; align-items: center; justify-content: center; border-radius: 50%; background: var(--color-soft-amber); color: var(--color-ink); font-size: 14px; font-weight: 700; }",
  ".step-en { display: block; color: var(--color-ink); font-size: 17px; font-weight: 700; line-height: 24px; }",
  ".step-zh { display: block; color: var(--color-slate); font-family: \"PingFang SC\", var(--typography-font-body); font-size: 14px; line-height: 22px; }",
  ".step.dark .step-en { color: var(--color-ink); }",
  ".step.dark .step-zh { color: var(--color-slate); }",
  ".step.dark .step-number { background: var(--color-primary); color: var(--color-primary-text); }",
  ".theme-paper .caption-left-en, .theme-paper .caption-right-en { color: var(--color-ink-soft); font-size: 13px; }",
  ".theme-paper .caption-left-zh, .theme-paper .caption-right-zh { color: var(--color-muted); font-size: 13px; }",
  ".navy-lead-en { color: var(--color-ink-soft); font-size: 18px; line-height: 30px; }",
  ".navy-lead-zh { color: var(--color-amber-text); font-family: \"PingFang SC\", var(--typography-font-body); font-size: 15px; }",
  ".navy-caption { color: var(--color-ink); font-size: 14px; text-align: center; }",
  ".trust-pillar { border: 1px solid var(--color-line); border-radius: 16px; background: var(--color-white); color: var(--color-ink); padding: 14px 18px 12px 76px; }",
  ".trust-number { position: absolute; left: 22px; top: 22px; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; border-radius: 50%; background: var(--color-primary); color: var(--color-primary-text); font-size: 13px; font-weight: 700; }",
  ".trust-title { color: var(--color-ink); font-size: 16px; font-weight: 700; }",
  ".trust-copy { color: var(--color-slate); white-space: pre-line; font-size: 12px; line-height: 1.18; }",
  ".health-date { color: var(--color-slate); font-size: 11px; text-align: right; }",
  ".plan { border: 1px solid var(--color-line); border-radius: 20px; background: var(--color-white); box-shadow: var(--slide-shadow); padding: 20px; }",
  ".plan.recommended { border-color: var(--color-primary); background: var(--color-soft-amber); color: var(--color-ink); }",
  ".plan-name { color: var(--color-ink); font-family: var(--typography-font-heading); font-size: 25px; font-weight: 700; }",
  ".plan.recommended .plan-name { color: var(--color-ink); }",
  ".plan-zh { color: var(--color-slate); font-family: \"PingFang SC\", var(--typography-font-body); font-size: 14px; }",
  ".plan.recommended .plan-zh { color: var(--color-amber-text); }",
  ".plan-price { color: var(--color-ink); font-size: 38px; line-height: 44px; font-weight: 700; }",
  ".plan.recommended .plan-price { color: var(--color-ink); }",
  ".plan-currency { color: var(--color-slate); font-size: 13px; text-align: right; }",
  ".plan.recommended .plan-currency { color: var(--color-amber-text); }",
  ".plan-rule { background: var(--color-line); }",
  ".plan.recommended .plan-rule { background: var(--color-primary); }",
  ".plan-limit { color: var(--color-ink); font-size: 13px; }",
  ".plan.recommended .plan-limit { color: var(--color-ink); }",
  ".plan-limit-zh { color: var(--color-slate); font-family: \"PingFang SC\", var(--typography-font-body); font-size: 12px; }",
  ".plan.recommended .plan-limit-zh { color: var(--color-amber-text); }",
  ".pricing-note { color: var(--color-slate); font-size: 13px; }",
  ".pricing-note-zh { color: var(--color-muted); font-family: \"PingFang SC\", var(--typography-font-body); font-size: 12px; }",
  ".edition-note { color: var(--color-amber-text); font-size: 11px; }",
  ".cta-url { color: var(--color-amber-text); font-size: 18px; font-weight: 700; }",
  ".cta-zh { color: var(--color-slate); font-family: \"PingFang SC\", var(--typography-font-body); font-size: 14px; text-align: right; }",
  ".footer { display: flex; align-items: center; justify-content: space-between; border-top: 1px solid var(--color-line); color: var(--color-muted); font-size: 11px; }",
  ".footer.navy { border-top-color: var(--color-line); color: var(--color-muted); }",
  ".nav-controls { position: fixed; z-index: 50; left: 50%; bottom: 18px; transform: translateX(-50%); display: flex; align-items: center; gap: 14px; color: var(--color-muted); font-size: 12px; }",
  ".nav-btn { width: 34px; height: 34px; border: 1px solid var(--color-line); border-radius: 50%; background: color-mix(in srgb, var(--color-paper) 92%, transparent); color: var(--color-ink); cursor: pointer; font-size: 16px; }",
  ".nav-btn:hover { background: var(--color-primary); border-color: var(--color-primary); }",
  ".progress-bar { position: fixed; z-index: 60; left: 0; top: 0; height: 3px; width: 10%; background: var(--color-primary); transition: width .233s ease; }",
  "@media (min-width: 769px) { .slide-deck { max-width: calc(100vh * 16 / 9); max-height: calc(100vw * 9 / 16); margin: auto; position: absolute; inset: 0; } }",
  "@media (max-width: 768px) { body { overflow: auto; } .slide-deck { width: 100vw; height: 56.25vw; min-height: 480px; transform-origin: top left; } .slide { transform: scale(.75); transform-origin: top left; width: 133.3333%; height: 133.3333%; } .nav-controls { bottom: 8px; } }",
  "@media (prefers-reduced-motion: reduce) { *, *::before, *::after { transition: none !important; animation: none !important; } }",
];

function buildHtml() {
  const slideMarkup = slides.map(buildHtmlSlide).join("\n");
  const script = [
    "let current = 1;",
    "const slideEls = Array.from(document.querySelectorAll('.slide'));",
    "const total = slideEls.length;",
    "const counter = document.getElementById('counter');",
    "const progress = document.getElementById('progress');",
    "function showSlide(n) { current = Math.max(1, Math.min(total, n)); slideEls.forEach((el, i) => el.classList.toggle('active', i === current - 1)); counter.textContent = current + ' / ' + total; progress.style.width = (current / total * 100) + '%'; }",
    "function nextSlide() { showSlide(current + 1); }",
    "function prevSlide() { showSlide(current - 1); }",
    "document.querySelectorAll('[data-action=next]').forEach((el) => el.addEventListener('click', nextSlide));",
    "document.querySelectorAll('[data-action=prev]').forEach((el) => el.addEventListener('click', prevSlide));",
    "document.addEventListener('keydown', (event) => { if (event.key === 'ArrowRight' || event.key === ' ') { event.preventDefault(); nextSlide(); } if (event.key === 'ArrowLeft') { event.preventDefault(); prevSlide(); } });",
    "document.addEventListener('click', (event) => { if (!event.target.closest('.nav-controls') && !event.target.closest('button')) nextSlide(); });",
    "showSlide(1);",
  ].join("\n");
  return [
    "<!doctype html>",
    '<html lang="zh-Hans">',
    "<head>",
    '<meta charset="utf-8">',
    '<meta name="viewport" content="width=device-width, initial-scale=1">',
    "<title>PWE Studio · Customer Roadshow / 客户路演版</title>",
    '<link rel="stylesheet" href="roadshow-assets/design-tokens.css">',
    "<style>" + HTML_CSS.join("\n") + "</style>",
    "</head>",
    "<body>",
    '<main class="slide-deck" aria-label="PWE Studio customer roadshow deck">',
    slideMarkup,
    "</main>",
    hFooterMeta(),
    "<script>" + script + "</script>",
    "</body>",
    "</html>",
  ].join("\n");
}

async function main() {
  await fs.mkdir(SALES_DIR, { recursive: true });
  await Promise.all(Object.values(ASSETS).map((asset) => assetBytes(asset)));
  await fs.writeFile(HTML_PATH, buildHtml(), "utf8");
  await buildPptx();
  console.log("Wrote " + HTML_PATH);
  console.log("Wrote " + PPTX_PATH);
  console.log("Preview: " + PREVIEW_DIR);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
