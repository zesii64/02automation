const { chromium } = require("playwright");
const path = require("path");

(async () => {
  const reportPath = path.resolve(
    "d:/11automation/02automation/10-Collection_Inspection/10-Collection_Inspection/reports/Collection_Operations_Report_v3_6_2026-04-18.html"
  );
  const url = "file:///" + reportPath.replace(/\\/g, "/");

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();

  const errors = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") {
      errors.push(msg.text());
    }
  });
  page.on("pageerror", (err) => {
    errors.push("PAGEERROR: " + err.message);
  });

  await page.goto(url, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(1500);

  const clickChecks = [];
  const checks = [
    { name: "TL role button", sel: "button[onclick*=\"switchRole('TL')\"]" },
    { name: "STL role button", sel: "button[onclick*=\"switchRole('STL')\"]" },
    { name: "Data role button", sel: "button[onclick*=\"switchRole('DATA')\"]" },
    { name: "TL date select", sel: "#tl-date-select" },
    { name: "TL group select", sel: "#tl-group-select" },
    { name: "STL module select", sel: "#stl-module-select" },
    { name: "Data subtab trend", sel: "#subtab-trend" },
  ];

  for (const c of checks) {
    const el = await page.$(c.sel);
    if (!el) {
      clickChecks.push(`${c.name}: NOT_FOUND`);
      continue;
    }
    const box = await el.boundingBox();
    const disabled = await el.evaluate((n) => n.disabled === true);
    clickChecks.push(`${c.name}: FOUND disabled=${disabled} box=${!!box}`);
    if (!disabled && box) {
      try {
        await el.click({ timeout: 2000 });
        clickChecks.push(`${c.name}: CLICK_OK`);
      } catch (e) {
        clickChecks.push(`${c.name}: CLICK_FAIL ${e.message}`);
      }
    }
  }

  console.log("=== ERRORS ===");
  if (errors.length === 0) console.log("(none)");
  for (const e of errors) console.log(e);
  console.log("=== CLICKS ===");
  for (const c of clickChecks) console.log(c);

  await browser.close();
})();
