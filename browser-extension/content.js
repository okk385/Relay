chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type !== "relay:deliver-to-chatgpt") return false;
  deliverPrompt(String(message.prompt ?? ""))
    .then(() => sendResponse({ ok: true }))
    .catch((error) => sendResponse({ ok: false, error: error.message }));
  return true;
});

async function deliverPrompt(prompt) {
  if (!prompt.trim()) throw new Error("Relay prompt is empty");
  if (isGenerationActive()) {
    throw new Error("ChatGPT is currently generating; Relay will retry later");
  }

  const composer = await waitForComposer();
  if (!isComposerEmpty(composer)) {
    throw new Error("ChatGPT composer contains a draft; Relay will not overwrite it");
  }

  composer.focus();
  insertText(composer, prompt);
  await delay(200);

  const sendButton = findSendButton(composer);
  if (sendButton && !sendButton.disabled) {
    sendButton.click();
    return;
  }

  const form = composer.closest("form");
  if (form?.requestSubmit) {
    form.requestSubmit();
    return;
  }
  throw new Error("Could not find an enabled ChatGPT send control");
}

function isGenerationActive() {
  return Boolean(
    document.querySelector('[data-testid="stop-button"]') ||
      [...document.querySelectorAll("button")].some((button) =>
        /stop generating|停止生成/i.test(button.getAttribute("aria-label") ?? ""),
      ),
  );
}

async function waitForComposer(timeoutMs = 10000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    const composer = findComposer();
    if (composer) return composer;
    await delay(250);
  }
  throw new Error("Could not find the ChatGPT composer");
}

function findComposer() {
  const selectors = [
    "#prompt-textarea",
    'textarea[data-testid="composer-text-input"]',
    'div[contenteditable="true"][data-lexical-editor="true"]',
    'textarea[placeholder]',
    'div[contenteditable="true"]',
  ];
  for (const selector of selectors) {
    const element = document.querySelector(selector);
    if (element && isVisible(element)) return element;
  }
  return null;
}

function isVisible(element) {
  const rect = element.getBoundingClientRect();
  const style = window.getComputedStyle(element);
  return rect.width > 0 && rect.height > 0 && style.visibility !== "hidden";
}

function isComposerEmpty(composer) {
  if (composer instanceof HTMLTextAreaElement || composer instanceof HTMLInputElement) {
    return composer.value.trim() === "";
  }
  return (composer.innerText ?? composer.textContent ?? "").trim() === "";
}

function insertText(composer, text) {
  if (composer instanceof HTMLTextAreaElement || composer instanceof HTMLInputElement) {
    const prototype =
      composer instanceof HTMLTextAreaElement
        ? HTMLTextAreaElement.prototype
        : HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(prototype, "value")?.set;
    if (!setter) throw new Error("Could not access the native input setter");
    setter.call(composer, text);
    composer.dispatchEvent(new Event("input", { bubbles: true }));
    composer.dispatchEvent(new Event("change", { bubbles: true }));
    return;
  }

  const selection = window.getSelection();
  const range = document.createRange();
  range.selectNodeContents(composer);
  selection?.removeAllRanges();
  selection?.addRange(range);
  const inserted = document.execCommand?.("insertText", false, text);
  if (!inserted) {
    composer.textContent = text;
    composer.dispatchEvent(
      new InputEvent("input", {
        bubbles: true,
        inputType: "insertText",
        data: text,
      }),
    );
  }
}

function findSendButton(composer) {
  const form = composer.closest("form");
  const roots = [form, document].filter(Boolean);
  const selectors = [
    '[data-testid="send-button"]',
    'button[aria-label="Send prompt"]',
    'button[aria-label="发送提示"]',
    'button[type="submit"]',
  ];
  for (const root of roots) {
    for (const selector of selectors) {
      const button = root.querySelector(selector);
      if (button && isVisible(button)) return button;
    }
  }
  return null;
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
