/**
 * Build and visually render the PWE Studio customer migration workbook.
 *
 * This script uses the bundled @oai/artifact-tool runtime. It deliberately
 * writes both to outputs/<thread-id>/ for review and to customer-resources/
 * for the product-home download route.
 */

import fs from "node:fs/promises";
import { fileURLToPath } from "node:url";

let artifactTool;
try {
  artifactTool = await import("@oai/artifact-tool");
} catch (error) {
  const moduleUrl = process.env.PWE_ARTIFACT_TOOL_MODULE_URL;
  if (!moduleUrl) {
    throw new Error(
      "Cannot load @oai/artifact-tool. Install it in the Node runtime or set " +
      "PWE_ARTIFACT_TOOL_MODULE_URL to its artifact_tool.mjs file URL.",
      { cause: error },
    );
  }
  artifactTool = await import(moduleUrl);
}
const { SpreadsheetFile, Workbook } = artifactTool;

const repositoryRoot = fileURLToPath(new URL("../../", import.meta.url));
const threadId = "019fac53-cea2-79a3-96a9-37e5de2b46a3";
const outputDir = `${repositoryRoot}outputs/${threadId}`;
const customerDir = `${repositoryRoot}customer-resources`;
const outputPath = `${outputDir}/PWE_Studio_Data_Import_Template.xlsx`;
const customerPath = `${customerDir}/PWE_Studio_Data_Import_Template.xlsx`;

const workbook = Workbook.create();
const instructions = workbook.worksheets.add("Instructions");
const students = workbook.worksheets.add("Students");
const courses = workbook.worksheets.add("Courses");
const packages = workbook.worksheets.add("Packages");
const fieldGuide = workbook.worksheets.add("Field Guide");

const palette = {
  forest: "#173F3A",
  forestDeep: "#0E2B28",
  gold: "#D7A93D",
  sage: "#DCE9DF",
  paper: "#FFFDF8",
  line: "#D7E0DC",
  ink: "#15312E",
  muted: "#5D716D",
  warning: "#FFF4D6",
};

function styleTitle(sheet, range, title) {
  const titleRange = sheet.getRange(range);
  titleRange.merge();
  titleRange.values = [[title]];
  titleRange.format = {
    fill: palette.forestDeep,
    font: { bold: true, color: "#FFFFFF", size: 20 },
    verticalAlignment: "center",
  };
  titleRange.format.rowHeight = 34;
}

function styleTableHeader(range) {
  range.format = {
    fill: palette.forest,
    font: { bold: true, color: "#FFFFFF" },
    verticalAlignment: "center",
    wrapText: true,
    borders: { preset: "outside", style: "thin", color: palette.forestDeep },
  };
  range.format.rowHeight = 34;
}

function styleDataArea(range) {
  range.format = {
    font: { color: palette.ink, size: 10 },
    verticalAlignment: "center",
    borders: {
      insideHorizontal: { style: "thin", color: palette.line },
      bottom: { style: "thin", color: palette.line },
    },
  };
}

instructions.showGridLines = false;
styleTitle(instructions, "A1:H1", "PWE Studio · Customer Data Import Template");
instructions.getRange("A3:H3").merge();
instructions.getRange("A3:H3").values = [[
  "Use this workbook for a structured migration assessment. PWE Studio can support mapping and import, but cannot guarantee that an arbitrary CSV/Excel file is standardised or ready to import without review and clean-up.",
]];
instructions.getRange("A3:H3").format = {
  fill: palette.warning,
  font: { bold: true, color: palette.ink },
  wrapText: true,
  verticalAlignment: "center",
  borders: { preset: "outside", style: "thin", color: palette.gold },
};
instructions.getRange("A3:H3").format.rowHeight = 58;
instructions.getRange("A5:B14").values = [
  ["Step", "What to do"],
  ["1", "Keep the worksheet names and column headers unchanged."],
  ["2", "Delete the fictional sample rows before supplying customer data."],
  ["3", "Use one stable external ID per student, course and package."],
  ["4", "Use dates in YYYY-MM-DD format and Australian mobile numbers where available."],
  ["5", "Do not paste passwords, payment-card details, medical records or identity documents."],
  ["6", "Complete the Field Guide checks before sending the file for assessment."],
  ["7", "PWE Studio will return a mapping report, exceptions list and quoted clean-up scope."],
  ["8", "Import occurs only after written approval and a recoverable backup/checkpoint."],
  ["Support", "Open the PWE Studio product home and use the Mail or Messages support action."],
];
styleTableHeader(instructions.getRange("A5:B5"));
styleDataArea(instructions.getRange("A6:B14"));
instructions.getRange("A15:H15").merge();
instructions.getRange("A15:H15").values = [[
  "Privacy: Use the minimum information needed for studio operations. Obtain the customer's authority before transferring personal information.",
]];
instructions.getRange("A15:H15").format = {
  fill: palette.sage,
  font: { color: palette.ink, italic: true },
  wrapText: true,
};
instructions.getRange("A15:H15").format.rowHeight = 40;
instructions.getRange("A:A").format.columnWidth = 15;
instructions.getRange("B:B").format.columnWidth = 76;
instructions.freezePanes.freezeRows(5);

const studentHeaders = [
  "external_student_id", "first_name", "last_name", "display_name", "status",
  "birth_date", "enrolled_on", "parent_guardian_name", "mobile", "email",
  "course_external_id", "opening_credits", "low_balance_threshold", "notes",
  "publication_consent", "source_system",
];
const studentRows = [
  ["STU-001", "Amelia", "Hart", "Amelia Hart", "active", "2015-04-16", "2026-02-03", "Sophie Hart", "0400000101", "family+amelia@example.com", "COURSE-PAINT-01", 8, 2, "Replace this fictional row with customer data", "no", "Current CMS"],
  ["STU-002", "Noah", "Lin", "Noah Lin", "trial", "2017-09-02", "2026-07-20", "Grace Lin", "0400000102", "family+noah@example.com", "COURSE-DRAW-01", 1, 2, "Use ISO dates YYYY-MM-DD", "no", "Spreadsheet"],
];
students.showGridLines = false;
students.getRange("A1:P3").values = [studentHeaders, ...studentRows];
styleTableHeader(students.getRange("A1:P1"));
styleDataArea(students.getRange("A2:P3"));
students.tables.add("A1:P3", true, "StudentsImportTable");
students.getRange("E2:E55").dataValidation = { rule: { type: "list", values: ["active", "trial", "inactive"] } };
students.getRange("O2:O55").dataValidation = { rule: { type: "list", values: ["yes", "no"] } };
students.getRange("L2:M55").dataValidation = { rule: { type: "decimal", operator: "between", formula1: 0, formula2: 99999 } };
students.getRange("L2:M55").setNumberFormat("0.00");
students.getRange("F2:G55").setNumberFormat("yyyy-mm-dd");
students.getRange("A:P").format.columnWidth = 18;
students.getRange("D:D").format.columnWidth = 22;
students.getRange("H:H").format.columnWidth = 24;
students.getRange("J:J").format.columnWidth = 30;
students.getRange("N:N").format.columnWidth = 42;
students.freezePanes.freezeRows(1);
students.freezePanes.freezeColumns(1);
students.getRange("E2:E55").conditionalFormats.add("containsText", {
  text: "inactive",
  format: { fill: "#FEE2E2", font: { color: "#991B1B" } },
});

const courseHeaders = [
  "external_course_id", "name", "description", "category", "age_range",
  "duration_minutes", "credit_unit", "default_credit_debit", "price_aud",
];
const courseRows = [
  ["COURSE-PAINT-01", "Foundation Painting", "Colour, composition and confident mark-making.", "Visual Arts", "7–11", 75, "credits", 1, 45],
  ["COURSE-DRAW-01", "Creative Drawing", "Observation, imagination and mixed-media drawing.", "Drawing", "6–10", 60, "credits", 1, 38],
];
courses.showGridLines = false;
courses.getRange("A1:I3").values = [courseHeaders, ...courseRows];
styleTableHeader(courses.getRange("A1:I1"));
styleDataArea(courses.getRange("A2:I3"));
courses.tables.add("A1:I3", true, "CoursesImportTable");
courses.getRange("F2:F55").dataValidation = { rule: { type: "whole", operator: "between", formula1: 15, formula2: 480 } };
courses.getRange("G2:G55").dataValidation = { rule: { type: "list", values: ["credits"] } };
courses.getRange("H2:H55").dataValidation = { rule: { type: "decimal", operator: "between", formula1: 0.25, formula2: 20 } };
courses.getRange("I2:I55").setNumberFormat("$0.00");
courses.getRange("A:I").format.columnWidth = 20;
courses.getRange("C:C").format.columnWidth = 48;
courses.freezePanes.freezeRows(1);

const packageHeaders = [
  "external_package_id", "course_external_id", "name", "credits",
  "price_aud", "expires_after_days", "active", "notes",
];
const packageRows = [
  ["PACK-PAINT-10", "COURSE-PAINT-01", "10-Class Studio Pack", 10, 420, 120, "yes", "Fictional sample"],
  ["PACK-DRAW-01", "COURSE-DRAW-01", "First Studio Visit", 1, 25, 30, "yes", "Fictional sample"],
];
packages.showGridLines = false;
packages.getRange("A1:H3").values = [packageHeaders, ...packageRows];
styleTableHeader(packages.getRange("A1:H1"));
styleDataArea(packages.getRange("A2:H3"));
packages.tables.add("A1:H3", true, "PackagesImportTable");
packages.getRange("G2:G55").dataValidation = { rule: { type: "list", values: ["yes", "no"] } };
packages.getRange("D2:D55").dataValidation = { rule: { type: "decimal", operator: "between", formula1: 0.25, formula2: 9999 } };
packages.getRange("E2:E55").setNumberFormat("$0.00");
packages.getRange("A:H").format.columnWidth = 22;
packages.getRange("H:H").format.columnWidth = 36;
packages.freezePanes.freezeRows(1);

const guideRows = [
  ["Students", "external_student_id", "Yes", "Unique text", "STU-001", "Stable key used to reconcile updates; never reuse for another person."],
  ["Students", "first_name", "Yes", "Text", "Amelia", "Student legal/preferred first name as agreed with the customer."],
  ["Students", "display_name", "Yes", "Text", "Amelia Hart", "Name shown to authorised studio staff."],
  ["Students", "status", "Yes", "active | trial | inactive", "active", "Archived records are assessed separately."],
  ["Students", "birth_date", "No", "YYYY-MM-DD", "2015-04-16", "Leave blank when not required for operations."],
  ["Students", "mobile", "Recommended", "Australian mobile", "0400000101", "Use the contact number authorised by the family."],
  ["Students", "opening_credits", "Yes", "Number >= 0", "8", "Must be reconciled to the source system at the migration cut-off."],
  ["Students", "publication_consent", "Yes", "yes | no", "no", "No is the safe default; historical consent evidence is reviewed separately."],
  ["Courses", "external_course_id", "Yes", "Unique text", "COURSE-PAINT-01", "Referenced by students and packages."],
  ["Courses", "duration_minutes", "Yes", "Whole number", "75", "Planned class duration, not attendance history."],
  ["Packages", "credits", "Yes", "Number > 0", "10", "Credits included in the package."],
  ["Packages", "price_aud", "Yes", "AUD number", "420", "GST treatment is confirmed in the commercial order form."],
];
fieldGuide.showGridLines = false;
fieldGuide.getRange(`A1:F${guideRows.length + 1}`).values = [
  ["Sheet", "Field", "Required", "Format", "Example", "Validation and mapping note"],
  ...guideRows,
];
styleTableHeader(fieldGuide.getRange("A1:F1"));
styleDataArea(fieldGuide.getRange(`A2:F${guideRows.length + 1}`));
fieldGuide.tables.add(`A1:F${guideRows.length + 1}`, true, "ImportFieldGuideTable");
fieldGuide.getRange("A:F").format.columnWidth = 22;
fieldGuide.getRange("F:F").format.columnWidth = 68;
fieldGuide.getRange(`F2:F${guideRows.length + 1}`).format.wrapText = true;
fieldGuide.freezePanes.freezeRows(1);

await fs.mkdir(outputDir, { recursive: true });
await fs.mkdir(customerDir, { recursive: true });
const exported = await SpreadsheetFile.exportXlsx(workbook);
await exported.save(outputPath);
await fs.copyFile(outputPath, customerPath);

const inspection = await workbook.inspect({
  kind: "workbook,sheet,table",
  maxChars: 10000,
  tableMaxRows: 4,
  tableMaxCols: 8,
  tableMaxCellChars: 70,
});
await fs.writeFile(`${outputDir}/workbook-inspection.json`, JSON.stringify(inspection, null, 2));

for (const sheetName of ["Instructions", "Students", "Courses", "Packages", "Field Guide"]) {
  const preview = await workbook.render({ sheetName, autoCrop: "all", scale: 1, format: "png" });
  await fs.writeFile(`${outputDir}/${sheetName.replaceAll(" ", "-").toLowerCase()}.png`, new Uint8Array(await preview.arrayBuffer()));
}

console.log(JSON.stringify({ outputPath, customerPath, sheets: 5 }, null, 2));
