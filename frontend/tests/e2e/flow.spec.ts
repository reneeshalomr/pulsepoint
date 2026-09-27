import { test, expect } from "@playwright/test";
test("complete huddle, export brief, retain session, and filter graph", async ({
  page,
}, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: /Good questions deserve/ }),
  ).toBeVisible();
  await page.screenshot({
    path: `../docs/screenshots/${testInfo.project.name}-home.png`,
    fullPage: true,
  });
  await page.getByRole("button", { name: /Try a sample question/ }).click();
  await page.getByRole("button", { name: "Start huddle", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Let’s get the question right." }),
  ).toBeVisible();
  await page.getByRole("button", { name: /Continue to evidence/ }).click();
  await expect(
    page.getByRole("heading", { name: "Dr. Maya Patel" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Request huddle", exact: true })
    .click();
  await page.getByRole("button", { name: "Use simulated response" }).click();
  await page.getByRole("button", { name: "Create huddle brief" }).click();
  await expect(
    page.getByRole("heading", { name: "Clarity, brought together." }),
  ).toBeVisible();
  await expect(
    page.getByText("SIMULATED OPINION", { exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: `../docs/screenshots/${testInfo.project.name}-brief.png`,
    fullPage: true,
  });
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download brief" }).click();
  expect((await download).suggestedFilename()).toBe(
    "pulsepoint-huddle-brief.txt",
  );
  await page.reload();
  await expect(
    page.getByRole("button", { name: /Treatment sequencing Demo case/ }),
  ).toHaveCount(2);
  await page
    .getByRole("button", { name: "Question graph", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "What HCPs are asking." }),
  ).toBeVisible();
  await page.getByRole("combobox").selectOption("Oncology");
  await expect(page.getByText("90", { exact: true })).toBeVisible();
  await page.screenshot({
    path: `../docs/screenshots/${testInfo.project.name}-graph.png`,
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  expect(errors).toEqual([]);
});
test("unsupported question has no fabricated match and search supports empty state", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByLabel("Clinical question", { exact: true })
    .fill("What evidence should I review for arrhythmia?");
  await page.getByRole("button", { name: "Start huddle", exact: true }).click();
  await page.getByRole("button", { name: /Continue to evidence/ }).click();
  await expect(
    page.getByRole("heading", { name: "No matching evidence in this demo" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "No expert match", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "My huddles", exact: true })
    .last()
    .click();
  await page.getByRole("textbox", { name: "Search huddles" }).fill("zzzzzz");
  await expect(
    page.getByRole("heading", { name: "No huddles found" }),
  ).toBeVisible();
});
test("voice gracefully falls back and about dialog can be closed with Escape", async ({
  page,
}) => {
  await page.addInitScript(() => {
    Object.defineProperty(window, "SpeechRecognition", { value: undefined });
    Object.defineProperty(window, "webkitSpeechRecognition", {
      value: undefined,
    });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Speak your question" }).click();
  await expect(
    page.getByText(
      "Voice input is unavailable in this browser. You can type your question below.",
    ),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "About this demo", exact: true })
    .last()
    .click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).not.toBeVisible();
});
