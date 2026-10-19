"""Run the whole dashboard script (webapp/static/app.js) in node against a small fake page, so a test drives the real
functions end to end instead of a hand-picked extract of them. Fabricated data only.

`run_dashboard(body)` loads app.js after the fake page and then runs `body`, which must print one JSON document with
`console.log`. Every element the script looks up exists (a permissive fake keyed by id); `fetch` answers from
`globalThis.FAKE_RESPONSES` (url prefix -> {status, json|text}, the longest matching prefix winning), else 404, and
records every request in `globalThis.REQUESTS` ({url, method, body}); timers run for real. The fakes do not parse
HTML: a test reads what was written into `innerHTML`, and stands in for a clicked or ticked element with a fake of
its own (`fakeElement`)."""
import json
import shutil
import subprocess
from pathlib import Path

NODE = shutil.which("node")
APP_JS = (Path(__file__).resolve().parents[1] / "webapp/static/app.js").read_text(encoding="utf-8")

FAKE_PAGE = r"""
// `event.target instanceof Element` must hold for the fakes.
globalThis.Element = class Element {};

function fakeClassList(el) {
  const names = () => el.className.split(/\s+/).filter(Boolean);
  const list = {
    add(...add) { el.className = [...new Set([...names(), ...add])].join(" "); },
    remove(...drop) { el.className = names().filter((name) => !drop.includes(name)).join(" "); },
    toggle(name, force) {
      const on = force === undefined ? !names().includes(name) : Boolean(force);
      if (on) list.add(name); else list.remove(name);
      return on;
    },
    contains(name) { return names().includes(name); },
  };
  return new Proxy(list, { get(target, key) {
    if (typeof key === "string" && /^\d+$/.test(key)) return names()[Number(key)];
    if (key === "length") return names().length;
    return target[key];
  } });
}

function fakeElement(id) {
  const el = Object.assign(Object.create(Element.prototype), {
    id, tagName: "DIV", textContent: "", innerHTML: "", value: "", checked: false, disabled: false, hidden: false,
    className: "", style: {}, dataset: {}, attributes: {}, children: [], listeners: {},
    setAttribute(key, value) { this.attributes[key] = String(value); },
    getAttribute(key) { return key in this.attributes ? this.attributes[key] : null; },
    removeAttribute(key) { delete this.attributes[key]; },
    hasAttribute(key) { return key in this.attributes; },
    addEventListener(type, handler) { (this.listeners[type] = this.listeners[type] || []).push(handler); },
    removeEventListener() {},
    dispatch(type, event) { (this.listeners[type] || []).forEach((handler) => handler(event)); },
    insertAdjacentHTML(where, html) {
      this.innerHTML = where === "afterbegin" ? html + this.innerHTML : this.innerHTML + html;
    },
    querySelector() { return null; }, querySelectorAll() { return []; }, closest() { return null; },
    contains() { return false; }, focus() {}, blur() {}, click() {}, scrollIntoView() {}, select() {},
    appendChild(child) { this.children.push(child); return child; }, remove() {}, replaceChildren() {},
    getBoundingClientRect() { return { x: 0, y: 0, width: 0, height: 0, top: 0, left: 0, right: 0, bottom: 0 }; },
  });
  Object.defineProperty(el, "classList", { get() { return fakeClassList(el); } });
  Object.defineProperty(el, "innerText", { get() { return String(el.innerHTML || el.textContent); } });
  return el;
}

const fakeElements = new Map();
function byId(id) {
  if (!fakeElements.has(id)) fakeElements.set(id, fakeElement(id));
  return fakeElements.get(id);
}
const fakeDocument = fakeElement("document");
fakeDocument.documentElement = fakeElement("html");
fakeDocument.body = fakeElement("body");
fakeDocument.getElementById = byId;
fakeDocument.querySelector = (selector) => byId(`query:${selector}`);
fakeDocument.querySelectorAll = () => [];
fakeDocument.createElement = (tag) => fakeElement(`new:${tag}`);
fakeDocument.execCommand = () => true;
Object.defineProperty(fakeDocument, "activeElement", { get() { return null; } });
globalThis.document = fakeDocument;
globalThis.window = globalThis;
const store = {};
globalThis.localStorage = { getItem: (key) => (key in store ? store[key] : null),
                            setItem: (key, value) => { store[key] = String(value); },
                            removeItem: (key) => { delete store[key]; } };
globalThis.sessionStorage = { getItem: () => null, setItem() {}, removeItem() {} };
globalThis.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} });
globalThis.scrollTo = () => {};
globalThis.requestAnimationFrame = (callback) => setTimeout(callback, 0);
try { Object.defineProperty(globalThis, "navigator", { value: { clipboard: { writeText: () => Promise.resolve() } }, configurable: true }); } catch (error) {}
globalThis.FAKE_RESPONSES = {};
globalThis.FETCHED = [];
globalThis.REQUESTS = [];
globalThis.fetch = (url, options = {}) => {
  const text = String(url);
  FETCHED.push(text);
  REQUESTS.push({ url: text, method: options.method || "GET", body: options.body || null });
  // The most specific answer wins: "/analysis/x/revenue-reviews" before "/analysis/x".
  const key = Object.keys(FAKE_RESPONSES).filter((prefix) => text.startsWith(prefix))
    .sort((a, b) => b.length - a.length)[0];
  const answer = key ? FAKE_RESPONSES[key] : { status: 404, text: "not found" };
  const body = "json" in answer ? JSON.stringify(answer.json) : String(answer.text || "");
  return Promise.resolve(new Response(body, { status: answer.status || 200,
                                              headers: { "Content-Type": "json" in answer ? "application/json" : "text/plain" } }));
};
globalThis.settle = () => new Promise((resolve) => setTimeout(resolve, 20));
"""


def run_dashboard(body: str) -> dict:
    """Load app.js on the fake page, run `body`, and return the JSON it printed."""
    script = FAKE_PAGE + "\n" + APP_JS + "\n;(async () => {\n" + body + "\n})().catch((error) => {"\
        " console.error(error && error.stack || String(error)); process.exit(1); });\n"
    result = subprocess.run([NODE, "-"], input=script, capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert result.returncode == 0, result.stderr[-4000:]
    return json.loads(result.stdout.strip().splitlines()[-1])
