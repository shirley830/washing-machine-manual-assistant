import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import fs from "node:fs";
import http from "node:http";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { chromium, webkit } from "playwright";


const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const requestBodies = [];

function listen(server, port = 0) {
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(port, "127.0.0.1", () => resolve(server.address().port));
  });
}

async function freePort() {
  const server = net.createServer();
  const port = await listen(server);
  await new Promise((resolve) => server.close(resolve));
  return port;
}

function createMockOpenRouter() {
  return http.createServer((request, response) => {
    if (request.method !== "POST" || request.url !== "/api/v1/chat/completions") {
      response.writeHead(404).end();
      return;
    }

    let rawBody = "";
    request.setEncoding("utf8");
    request.on("data", (chunk) => { rawBody += chunk; });
    request.on("end", () => {
      const payload = JSON.parse(rawBody);
      requestBodies.push(payload);

      if (requestBodies.length === 3) {
        response.writeHead(401, { "Content-Type": "application/json" });
        response.end(JSON.stringify({
          error: {
            message: "Invalid API key used by the deterministic test server.",
            type: "invalid_request_error",
            code: "invalid_api_key"
          }
        }));
        return;
      }

      if (requestBodies.length === 4) {
        response.writeHead(200, { "Content-Type": "application/json" });
        response.end(JSON.stringify({
          id: "mock-empty-response",
          object: "chat.completion",
          created: 1,
          model: payload.model,
          choices: [{
            index: 0,
            message: { role: "assistant", content: null },
            finish_reason: "stop"
          }],
          usage: {
            prompt_tokens: 120,
            completion_tokens: 0,
            total_tokens: 120,
            cost: 0
          }
        }));
        return;
      }

      const prompt = payload.messages?.at(-1)?.content ?? "";
      const content = prompt.includes("Model: ZWG1120M")
        ? "Error code E30 means that the washer door is not closed. [E1]"
        : "Error code E:30 / -80 means that the drain pipe or water drain hose is blocked. [E1]";
      response.writeHead(200, { "Content-Type": "application/json" });
      response.end(JSON.stringify({
        id: `mock-${requestBodies.length}`,
        object: "chat.completion",
        created: 1,
        model: payload.model,
        choices: [{
          index: 0,
          message: { role: "assistant", content },
          finish_reason: "stop"
        }],
        usage: {
          prompt_tokens: 120,
          completion_tokens: 20,
          total_tokens: 140,
          cost: 0.000022
        }
      }));
    });
  });
}

function pythonExecutable() {
  if (process.env.PYTHON) return process.env.PYTHON;
  const localPython = path.join(projectRoot, ".venv", "bin", "python");
  return fs.existsSync(localPython) ? localPython : "python3";
}

async function waitForApp(url, processOutput) {
  const deadline = Date.now() + 45_000;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch {
      // Streamlit is still starting.
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`Streamlit did not start.\n${processOutput()}`);
}

async function chooseOption(page, label, option) {
  const combobox = page.getByRole("combobox", { name: label });
  await combobox.click();
  await page.getByRole("option", { name: option, exact: true }).click();
}

async function submitQuestion(page, question) {
  await page.getByRole("textbox", { name: "Ask about this machine" }).fill(question);
  await page.getByRole("button", { name: "ASK", exact: true }).click();
}

async function waitForInputValue(page, label, expected) {
  const deadline = Date.now() + 15_000;
  const combobox = page.getByRole("combobox", { name: label });
  while (Date.now() < deadline) {
    if (await combobox.inputValue() === expected) return;
    await page.waitForTimeout(100);
  }
  throw new Error(`${label} did not update to ${expected}`);
}

function center(rect) {
  return rect.x + rect.width / 2;
}

async function run() {
  const browserName = process.env.PLAYWRIGHT_BROWSER ?? "chromium";
  assert.ok(["chromium", "webkit"].includes(browserName), `Unsupported browser: ${browserName}`);
  const browserType = browserName === "webkit" ? webkit : chromium;
  const mockServer = createMockOpenRouter();
  const mockPort = await listen(mockServer);
  const appPort = await freePort();
  const tempDirectory = fs.mkdtempSync(path.join(os.tmpdir(), "wm-assistant-e2e-"));
  let streamlitOutput = "";
  const streamlit = spawn(
    pythonExecutable(),
    [
      "-m", "streamlit", "run", "streamlit_app.py",
      "--server.address", "127.0.0.1",
      "--server.port", String(appPort),
      "--server.headless", "true"
    ],
    {
      cwd: projectRoot,
      env: {
        ...process.env,
        OPENROUTER_API_KEY: "not-a-real-key-used-only-by-the-local-test-server",
        OPENROUTER_MODEL: "test/mock-model",
        OPENROUTER_BASE_URL: `http://127.0.0.1:${mockPort}/api/v1`,
        WM_ASSISTANT_USAGE_LOG: path.join(tempDirectory, "api_usage.jsonl")
      },
      stdio: ["ignore", "pipe", "pipe"]
    }
  );
  streamlit.stdout.on("data", (data) => { streamlitOutput += data.toString(); });
  streamlit.stderr.on("data", (data) => { streamlitOutput += data.toString(); });

  let browser;
  try {
    const appUrl = `http://127.0.0.1:${appPort}`;
    await waitForApp(appUrl, () => streamlitOutput);
    const launchOptions = { headless: true };
    if (browserName === "chromium" && process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE) {
      launchOptions.executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE;
    }
    browser = await browserType.launch(launchOptions);

    const desktop = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    await desktop.goto(appUrl, { waitUntil: "networkidle" });
    await desktop.locator(".wm-title").waitFor();
    assert.equal(await desktop.getByRole("heading", { level: 1 }).innerText(), "Every cycle,\nmade clear.");
    assert.equal(await desktop.getByRole("combobox", { name: "Brand" }).inputValue(), "Gaggenau");
    assert.equal(await desktop.getByRole("combobox", { name: "Exact model" }).inputValue(), "WM260164");

    const layout = await desktop.evaluate(() => {
      const [firstLine, secondLine] = document.querySelectorAll(".wm-title-line");
      const first = firstLine.getBoundingClientRect();
      const second = secondLine.getBoundingClientRect();
      const eyebrow = document.querySelector(".wm-eyebrow").getBoundingClientRect();
      const promise = document.querySelector(".wm-promise").getBoundingClientRect();
      const logo = document.querySelector(".wm-logo").getBoundingClientRect();
      const wordmark = document.querySelector(".wm-wordmark").getBoundingClientRect();
      return {
        overflow: document.documentElement.scrollWidth - innerWidth,
        first: { x: first.x, width: first.width },
        second: { x: second.x, width: second.width },
        eyebrowCenter: eyebrow.left + eyebrow.width / 2,
        promiseCenter: promise.left + promise.width / 2,
        brandGroupCenter: (logo.left + wordmark.right) / 2
      };
    });
    assert.ok(layout.overflow <= 0, "desktop must not scroll horizontally");
    assert.ok(Math.abs(center(layout.first) - center(layout.second)) < 1, "title lines must share a visual center");
    assert.ok(Math.abs(layout.eyebrowCenter - center(layout.first)) < 1, "eyebrow must align with the title center");
    assert.ok(Math.abs(layout.promiseCenter - center(layout.first)) < 1, "supporting copy must align with the title center");
    assert.ok(Math.abs(layout.brandGroupCenter - center(layout.first)) < 1, "logo and wordmark must align with the title center");

    await submitQuestion(desktop, "What does error code E:30 / -80 mean?");
    await desktop.locator(".wm-answer").waitFor();
    await assertText(desktop.locator(".wm-answer-copy"), "drain pipe or water drain hose is blocked");
    await assertText(desktop.locator(".wm-source-meta"), "Page 62");
    assert.match(await desktop.locator(".wm-source a").getAttribute("href"), /^https:\/\//);
    assert.equal(await desktop.getByText("ANSWER TIME", { exact: true }).count(), 0);
    assert.equal(await desktop.getByText("ESTIMATED COST", { exact: true }).count(), 0);

    await chooseOption(desktop, "Brand", "Zanussi");
    await waitForInputValue(desktop, "Exact model", "ZWG1120M");
    await submitQuestion(desktop, "What does error code E30 mean?");
    await desktop.locator(".wm-answer-copy").waitFor();
    await assertText(desktop.locator(".wm-answer-copy"), "washer door is not closed");
    await assertText(desktop.locator(".wm-source-meta"), "Page 16");

    await chooseOption(desktop, "Brand", "SMEG");
    await submitQuestion(desktop, "How do I connect this washer to the Home Connect app?");
    await desktop.locator(".wm-refusal").waitFor();
    await assertText(desktop.locator(".wm-refusal"), "does not support this answer");
    assert.equal(requestBodies.length, 2, "local refusal must not call OpenRouter");

    await submitQuestion(desktop, "   ");
    await assertText(desktop.getByRole("alert"), "Enter a question");
    assert.equal(await desktop.locator(".wm-answer-shell").count(), 0, "an invalid submission must clear the previous result");

    await chooseOption(desktop, "Brand", "Gaggenau");
    await waitForInputValue(desktop, "Exact model", "WM260164");
    await submitQuestion(desktop, "What does error code E:30 / -80 mean?");
    await assertText(desktop.getByRole("alert"), "OpenRouter rejected the API key");
    assert.equal(await desktop.locator(".wm-answer-shell").count(), 0, "an API failure must not leave a stale answer");

    await submitQuestion(desktop, "What does error code E:30 / -80 mean?");
    await assertText(desktop.getByRole("alert"), "OpenRouter did not return a usable answer");
    assert.equal(await desktop.locator(".wm-answer-shell").count(), 0, "an empty model response must not leave a stale answer");

    assert.match(requestBodies[0].messages.at(-1).content, /Model: WM260164/);
    assert.match(requestBodies[1].messages.at(-1).content, /Model: ZWG1120M/);

    const mobile = await browser.newPage({ viewport: { width: 390, height: 844 }, isMobile: true });
    await mobile.goto(appUrl, { waitUntil: "networkidle" });
    await mobile.locator(".wm-title").waitFor();
    const mobileLayout = await mobile.evaluate(() => {
      const button = document.querySelector('[data-testid="stFormSubmitButton"] button').getBoundingClientRect();
      const [firstLine, secondLine] = document.querySelectorAll(".wm-title-line");
      const first = firstLine.getBoundingClientRect();
      const second = secondLine.getBoundingClientRect();
      return {
        overflow: document.documentElement.scrollWidth - innerWidth,
        button: { width: button.width, height: button.height },
        first: { x: first.x, width: first.width },
        second: { x: second.x, width: second.width }
      };
    });
    assert.ok(mobileLayout.overflow <= 0, "mobile must not scroll horizontally");
    assert.ok(mobileLayout.button.width >= 44 && mobileLayout.button.height >= 44, "mobile ASK target must be at least 44px");
    assert.ok(Math.abs(center(mobileLayout.first) - center(mobileLayout.second)) < 1, "mobile title lines must share a visual center");

    console.log(`PASS ${browserName} initial desktop layout and form state`);
    console.log("PASS Gaggenau and Zanussi model-collision answers with exact pages");
    console.log("PASS evidence-gated refusal without an API call");
    console.log("PASS empty-input, authentication, and empty-response errors clear stale results");
    console.log("PASS mobile overflow, title alignment, and touch-target checks");
    console.log(`PASS ${requestBodies.length} deterministic mock OpenRouter requests; no paid API used`);
  } finally {
    if (browser) await browser.close();
    streamlit.kill("SIGTERM");
    await new Promise((resolve) => mockServer.close(resolve));
    fs.rmSync(tempDirectory, { recursive: true, force: true });
  }
}

async function assertText(locator, expected) {
  const pattern = new RegExp(expected, "i");
  const deadline = Date.now() + 30_000;
  while (Date.now() < deadline) {
    if (await locator.count()) {
      const value = await locator.innerText();
      if (pattern.test(value)) return;
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  const finalValue = await locator.count() ? await locator.innerText() : "<missing>";
  assert.match(finalValue, pattern);
}

run().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
