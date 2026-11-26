import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import ts from "typescript";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

const require = createRequire(import.meta.url);

function loadTsModule(relPath, customRequires = {}) {
  const fullPath = path.resolve(relPath);
  const src = fs.readFileSync(fullPath, "utf8");
  const { outputText } = ts.transpileModule(src, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2020,
      jsx: ts.JsxEmit.React,
      esModuleInterop: true,
    },
  });
  const mod = { exports: {} };
  const req = (id) => {
    if (id in customRequires) return customRequires[id];
    if (id === "react") return React;
    if (id === "lucide-react") {
      return new Proxy(
        {},
        {
          get: (_t, prop) => (props) =>
            React.createElement("svg", { "data-icon": String(prop), ...props }),
        }
      );
    }
    return require(id);
  };
  new Function("module", "exports", "require", "React", outputText)(
    mod,
    mod.exports,
    req,
    React
  );
  return mod.exports;
}

const constantsMod = loadTsModule("src/lib/constants.ts");
const modalDialogMod = loadTsModule("src/components/ModalDialog.tsx");
const chatHistoryMod = loadTsModule("src/lib/chatHistory.ts");
const locationSearchMod = loadTsModule("src/lib/locationSearch.ts");
const alertsHookMod = loadTsModule("src/hooks/useAlerts.ts");

test("A11Y-01: AlertsManager renders WCAG dialog semantics, labelled fields, tablist roles, and 15-city support", () => {
  const { AlertsManager } = loadTsModule("src/components/AlertsManager.tsx", {
    "../lib/constants": constantsMod,
    "./ModalDialog": modalDialogMod,
  });

  const cities = [
    ...constantsMod.POPULAR_CITIES,
    { id: "varanasi", name: "Varanasi", state: "Uttar Pradesh", latitude: 25.31, longitude: 82.97 },
  ];

  const html = renderToStaticMarkup(
    React.createElement(AlertsManager, {
      isOpen: true,
      onClose: () => {},
      rules: [
        {
          id: "rule-1",
          city: "Varanasi",
          thresholdAqi: 200,
          enabled: true,
          createdAt: "2026-11-26T00:00:00Z",
        },
      ],
      history: [],
      cities,
      onAddRule: () => {},
      onToggleRule: () => {},
      onDeleteRule: () => {},
      onClearHistory: () => {},
    })
  );

  assert.match(html, /role="dialog"/);
  assert.match(html, /aria-modal="true"/);
  assert.match(html, /aria-labelledby="alerts-modal-title"/);
  assert.match(html, /aria-label="Close threshold alert manager"/);
  assert.match(html, /role="tablist"/);
  assert.match(html, /role="tab"/);
  assert.match(html, /for="alert-city-select"/);
  assert.match(html, /id="alert-city-select"/);
  assert.match(html, /for="alert-threshold-range"/);
  assert.match(html, /aria-label="Delete alert rule for Varanasi"/);
  assert.match(html, /Varanasi/);
});

test("A11Y-01 & PSA-03: MethodologyModal exposes dialog semantics and NH3 CPCB breakpoints", () => {
  const { MethodologyModal } = loadTsModule("src/components/MethodologyModal.tsx", {
    "./ModalDialog": modalDialogMod,
  });

  const html = renderToStaticMarkup(
    React.createElement(MethodologyModal, { isOpen: true, onClose: () => {} })
  );

  assert.match(html, /role="dialog"/);
  assert.match(html, /aria-modal="true"/);
  assert.match(html, /aria-labelledby="methodology-modal-title"/);
  assert.match(html, /aria-label="Close methodology modal"/);
  assert.match(html, /NH3 \(24h\)/);
  assert.match(html, /Model rolling concentration/);
});

test("A11Y-02 & CQ-03: Navbar aria-current, skip link, h1 landmark, and transform-free fadeIn keyframes", () => {
  const { Navbar } = loadTsModule("src/components/Navbar.tsx", {
    "../lib/constants": constantsMod,
  });

  const navHtml = renderToStaticMarkup(
    React.createElement(Navbar, {
      activeTab: "comparison",
      setActiveTab: () => {},
      selectedCity: "delhi",
      setSelectedCity: () => {},
      onOpenAlerts: () => {},
      onOpenMethodology: () => {},
      alertCount: 0,
    })
  );
  assert.match(navHtml, /aria-current="page"/);

  const layoutSrc = fs.readFileSync(path.resolve("src/app/layout.tsx"), "utf8");
  assert.match(layoutSrc, /href="#main-content"/);
  const pageSrc = fs.readFileSync(path.resolve("src/app/page.tsx"), "utf8");
  assert.match(pageSrc, /id="main-content"/);
  assert.match(pageSrc, /<h1\b/);
  const cssSrc = fs.readFileSync(path.resolve("src/app/globals.css"), "utf8");
  assert.doesNotMatch(cssSrc, /@keyframes fadeIn[\s\S]*transform:/);
});

test("SEC-03: sanitizeAlertRules and sanitizeAlertHistory reject malformed localStorage records", () => {
  const { sanitizeAlertRules, sanitizeAlertHistory, loadInitialAlertRules } = alertsHookMod;

  const cleanedRules = sanitizeAlertRules([
    { id: "r1", city: "New Delhi", thresholdAqi: 200, enabled: true, createdAt: "2026-11-26T00:00:00Z" },
    { id: "", city: "Mumbai", thresholdAqi: 200, enabled: true },
    { id: "r2", city: 123, thresholdAqi: 200, enabled: true },
    { id: "r3", city: "Delhi", thresholdAqi: 999, enabled: true },
    null,
  ]);
  assert.equal(cleanedRules.length, 1);
  assert.equal(cleanedRules[0].id, "r1");

  const cleanedHist = sanitizeAlertHistory([
    { id: "h1", city: "New Delhi", aqi: 255, category: "POOR", timestamp: "2026-11-26T00:00:00Z", message: "Alert" },
    { id: "h2", city: "Delhi", aqi: "NaN", category: "POOR", timestamp: "x", message: "bad" },
  ]);
  assert.equal(cleanedHist.length, 1);
  assert.equal(cleanedHist[0].id, "h1");

  // 1. No existing storage -> seeds default rule and persists it
  const storeEmptyKey = new Map();
  const mockStorage1 = {
    getItem: (k) => (storeEmptyKey.has(k) ? storeEmptyKey.get(k) : null),
    setItem: (k, v) => storeEmptyKey.set(k, v),
  };
  const seeded = loadInitialAlertRules(mockStorage1);
  assert.equal(seeded.length, 1);
  assert.equal(seeded[0].city, "New Delhi");
  assert.equal(JSON.parse(storeEmptyKey.get("airaware_alert_rules_v1")).length, 1);

  // 2. Stored "[]" -> deliberately empty rules remain empty on reload
  const storeDeliberateEmpty = new Map([["airaware_alert_rules_v1", "[]"]]);
  const reloadedEmpty = loadInitialAlertRules({
    getItem: (k) => (storeDeliberateEmpty.has(k) ? storeDeliberateEmpty.get(k) : null),
    setItem: (k, v) => storeDeliberateEmpty.set(k, v),
  });
  assert.deepEqual(reloadedEmpty, []);
  assert.equal(storeDeliberateEmpty.get("airaware_alert_rules_v1"), "[]");

  // 3. Malformed JSON -> recovers safely to [] without crashing
  const reloadedMalformed = loadInitialAlertRules({
    getItem: () => "{broken json",
    setItem: () => {},
  });
  assert.deepEqual(reloadedMalformed, []);

  // 4. Invalid rule objects inside stored array -> sanitized safely without re-seeding New Delhi
  const invalidStored = loadInitialAlertRules({
    getItem: () => JSON.stringify([{ id: "", city: "Mumbai", thresholdAqi: 200, enabled: true }, { bad: true }]),
    setItem: () => {},
  });
  assert.deepEqual(invalidStored, []);

  // 5. Full useAlerts hook cycle: mount (seeded) -> deleteRule(default) -> reload -> stays []
  const persistentMap = new Map();
  const prevLocalStorage = globalThis.localStorage;
  globalThis.localStorage = {
    getItem: (k) => (persistentMap.has(k) ? persistentMap.get(k) : null),
    setItem: (k, v) => persistentMap.set(k, v),
    removeItem: (k) => persistentMap.delete(k),
  };
  try {
    function mountUseAlerts() {
      const states = [];
      let idx = 0;
      let effectRan = false;
      const hookMod = loadTsModule("src/hooks/useAlerts.ts", {
        react: {
          useState(init) {
            const i = idx++;
            if (!(i in states)) states[i] = typeof init === "function" ? init() : init;
            const set = (updater) => {
              states[i] = typeof updater === "function" ? updater(states[i]) : updater;
            };
            return [states[i], set];
          },
          useEffect(fn) {
            if (!effectRan) {
              effectRan = true;
              fn();
            }
          },
          useCallback(fn) {
            return fn;
          },
        },
      });
      return {
        render() {
          idx = 0;
          return hookMod.useAlerts();
        },
      };
    }

    const firstMount = mountUseAlerts();
    firstMount.render(); // Initial mount triggers useEffect seeding
    const afterSeed = firstMount.render();
    assert.equal(afterSeed.rules.length, 1);
    afterSeed.deleteRule(afterSeed.rules[0].id);
    assert.equal(persistentMap.get("airaware_alert_rules_v1"), "[]");
    assert.deepEqual(firstMount.render().rules, []);

    // Simulate page reload with a fresh hook mount
    const reloadMount = mountUseAlerts();
    reloadMount.render(); // Initial mount reads "[]"
    const afterReload = reloadMount.render();
    assert.deepEqual(afterReload.rules, []);
    assert.equal(persistentMap.get("airaware_alert_rules_v1"), "[]");
  } finally {
    globalThis.localStorage = prevLocalStorage;
  }
});

test("PSA-01 & SEC-CSP: extractComparisonTargets handles explicit multi-city comparisons and rejects pollutant/time false positives; vercel.json forbids localhost CSP", () => {
  const { extractComparisonTargets } = chatHistoryMod;

  // Positive cases
  assert.deepEqual(
    extractComparisonTargets("Compare Delhi and Mumbai.", { city: "Bengaluru" }, constantsMod.POPULAR_CITIES),
    [{ city: "New Delhi" }, { city: "Mumbai" }]
  );
  assert.deepEqual(
    extractComparisonTargets("Delhi versus Chennai.", { city: "Mumbai" }, constantsMod.POPULAR_CITIES),
    [{ city: "New Delhi" }, { city: "Chennai" }]
  );
  assert.deepEqual(
    extractComparisonTargets(
      "Which city has better air quality, Mumbai or Hyderabad?",
      { city: "New Delhi" },
      constantsMod.POPULAR_CITIES
    ),
    [{ city: "Mumbai" }, { city: "Hyderabad" }]
  );
  assert.deepEqual(
    extractComparisonTargets(
      "How does this location compare to Mumbai or Bengaluru?",
      { city: "New Delhi", latitude: 28.6139, longitude: 77.209 },
      constantsMod.POPULAR_CITIES
    ),
    [{ city: "New Delhi" }, { city: "Mumbai" }, { city: "Bengaluru" }]
  );

  // Negative cases: never auto-add currentLocation for single city or mistake pollutant/time comparisons
  for (const query of [
    "Difference between PM2.5 and PM10 in Mumbai.",
    "Relationship between humidity and ozone in Chennai.",
    "Morning versus evening PM2.5 in Mumbai.",
    "What is the difference between today's and yesterday's AQI in Delhi?",
    "Compare with Chennai",
    "What is the dominant pollutant?",
  ]) {
    assert.equal(
      extractComparisonTargets(query, { city: "New Delhi", latitude: 28.6139, longitude: 77.209 }, constantsMod.POPULAR_CITIES),
      undefined,
      `Expected undefined for: ${query}`
    );
  }

  const vercelCfg = JSON.parse(fs.readFileSync(path.resolve("vercel.json"), "utf8"));
  const csp = vercelCfg.headers[0].headers.find((h) => h.key === "Content-Security-Policy").value;
  const connectSrc = csp.split(";").map((s) => s.trim()).find((d) => d.startsWith("connect-src"));
  assert.ok(connectSrc.includes("https://airaware-ai-backend.onrender.com"));
  assert.ok(!connectSrc.includes("127.0.0.1"));
  assert.ok(!connectSrc.includes("localhost"));
});

test("PSA-03: parseLocationSearchInput handles coordinates and city queries accurately", () => {
  const { parseLocationSearchInput } = locationSearchMod;

  assert.deepEqual(parseLocationSearchInput("28.6139, 77.2090"), {
    latitude: 28.6139,
    longitude: 77.209,
  });
  assert.deepEqual(parseLocationSearchInput("Chennai"), { city: "Chennai" });
  // Out-of-bounds coordinates fall back cleanly to city string so backend returns strict 422
  assert.deepEqual(parseLocationSearchInput("120.5, 77.2"), { city: "120.5, 77.2" });
  assert.equal(parseLocationSearchInput("   "), null);
});

function createFakeFocusable(id, overrides = {}) {
  const doc = overrides.doc;
  return {
    id,
    disabled: Boolean(overrides.disabled),
    hidden: Boolean(overrides.hidden),
    isConnected: overrides.isConnected !== undefined ? overrides.isConnected : true,
    focusCalls: 0,
    focus() {
      this.focusCalls += 1;
      if (doc) doc.activeElement = this;
    },
    hasAttribute(name) {
      return name === "hidden" ? Boolean(overrides.hidden) : false;
    },
    getAttribute(name) {
      if (name === "aria-hidden") return overrides.ariaHidden ? "true" : null;
      return null;
    },
  };
}

function createFakeKeyEvent(key, shiftKey = false) {
  return {
    key,
    shiftKey,
    defaultPrevented: false,
    preventDefault() {
      this.defaultPrevented = true;
    },
  };
}

test("A11Y-03: ModalDialog focus trap cycles Tab/Shift+Tab and handles empty focusables safely", () => {
  const { handleDialogKeyDown, getFocusableElements } = modalDialogMod;
  const doc = { activeElement: null };
  const btnFirst = createFakeFocusable("first", { doc });
  const btnMiddle = createFakeFocusable("middle", { doc });
  const btnLast = createFakeFocusable("last", { doc });
  const btnDisabled = createFakeFocusable("disabled", { doc, disabled: true });
  const btnHidden = createFakeFocusable("ariaHidden", { doc, ariaHidden: true });

  const panel = {
    id: "panel",
    focusCalls: 0,
    focus() {
      this.focusCalls += 1;
      doc.activeElement = this;
    },
    querySelectorAll() {
      return [btnFirst, btnDisabled, btnMiddle, btnHidden, btnLast];
    },
  };

  const focusables = getFocusableElements(panel);
  assert.deepEqual(
    focusables.map((el) => el.id),
    ["first", "middle", "last"]
  );

  const stack = ["d1"];

  // Tab from last wraps to first
  doc.activeElement = btnLast;
  const tabLast = createFakeKeyEvent("Tab", false);
  assert.equal(
    handleDialogKeyDown(tabLast, {
      panel,
      dialogId: "d1",
      onClose: () => {},
      stack,
      activeElement: doc.activeElement,
    }),
    true
  );
  assert.equal(tabLast.defaultPrevented, true);
  assert.equal(doc.activeElement, btnFirst);

  // Shift+Tab from first wraps to last
  const shiftTabFirst = createFakeKeyEvent("Tab", true);
  assert.equal(
    handleDialogKeyDown(shiftTabFirst, {
      panel,
      dialogId: "d1",
      onClose: () => {},
      stack,
      activeElement: doc.activeElement,
    }),
    true
  );
  assert.equal(shiftTabFirst.defaultPrevented, true);
  assert.equal(doc.activeElement, btnLast);

  // Focus on middle button allows native tab progression without preventDefault
  doc.activeElement = btnMiddle;
  const tabMiddle = createFakeKeyEvent("Tab", false);
  assert.equal(
    handleDialogKeyDown(tabMiddle, {
      panel,
      dialogId: "d1",
      onClose: () => {},
      stack,
      activeElement: doc.activeElement,
    }),
    false
  );
  assert.equal(tabMiddle.defaultPrevented, false);

  // Focus initially on panel or escaped outside clamps back inside dialog
  doc.activeElement = panel;
  const tabFromPanel = createFakeKeyEvent("Tab", false);
  assert.equal(
    handleDialogKeyDown(tabFromPanel, {
      panel,
      dialogId: "d1",
      onClose: () => {},
      stack,
      activeElement: doc.activeElement,
    }),
    true
  );
  assert.equal(tabFromPanel.defaultPrevented, true);
  assert.equal(doc.activeElement, btnFirst);

  doc.activeElement = null;
  const shiftTabOutside = createFakeKeyEvent("Tab", true);
  assert.equal(
    handleDialogKeyDown(shiftTabOutside, {
      panel,
      dialogId: "d1",
      onClose: () => {},
      stack,
      activeElement: doc.activeElement,
    }),
    true
  );
  assert.equal(shiftTabOutside.defaultPrevented, true);
  assert.equal(doc.activeElement, btnLast);

  // Dialog with zero focusable descendants keeps focus safely on panel without error
  const emptyPanel = {
    focusCalls: 0,
    focus() {
      this.focusCalls += 1;
      doc.activeElement = this;
    },
    querySelectorAll() {
      return [];
    },
  };
  const emptyTab = createFakeKeyEvent("Tab", false);
  assert.equal(
    handleDialogKeyDown(emptyTab, {
      panel: emptyPanel,
      dialogId: "d1",
      onClose: () => {},
      stack,
      activeElement: doc.activeElement,
    }),
    true
  );
  assert.equal(emptyTab.defaultPrevented, true);
  assert.equal(emptyPanel.focusCalls, 1);
  assert.equal(doc.activeElement, emptyPanel);
});

test("A11Y-04: ModalDialog lifecycle restores focus, deduplicates listeners across re-renders, and stacks Escape cleanly", () => {
  // Build an isolated ModalDialog harness with tracked DOM listeners & React hook runner
  const listeners = new Map();
  const pageTrigger = createFakeFocusable("page-trigger");
  const modalOneNestedTrigger = createFakeFocusable("modal-1-trigger");
  class FakeHTMLElement {
    constructor(data) {
      Object.assign(this, data);
    }
  }
  const wrappedPageTrigger = new FakeHTMLElement(pageTrigger);
  const wrappedNestedTrigger = new FakeHTMLElement(modalOneNestedTrigger);
  wrappedPageTrigger.focus = function () {
    this.focusCalls += 1;
    fakeDocument.activeElement = this;
  };
  wrappedNestedTrigger.focus = function () {
    this.focusCalls += 1;
    fakeDocument.activeElement = this;
  };

  const fakeDocument = {
    activeElement: wrappedPageTrigger,
    addEventListener(type, fn) {
      if (!listeners.has(type)) listeners.set(type, new Set());
      listeners.get(type).add(fn);
    },
    removeEventListener(type, fn) {
      listeners.get(type)?.delete(fn);
    },
  };

  const prevDoc = globalThis.document;
  const prevWin = globalThis.window;
  const prevHTMLElement = globalThis.HTMLElement;
  let timerId = 0;

  globalThis.document = fakeDocument;
  globalThis.HTMLElement = FakeHTMLElement;
  globalThis.window = {
    setTimeout(fn) {
      timerId += 1;
      fn();
      return timerId;
    },
    clearTimeout() {},
  };

  try {
    // Load ONE shared ModalDialog module bound to per-instance hook dispatcher
    let activeHooks = null;
    const sharedReact = {
      createElement(type, props, ...children) {
        if (type === "div" && props?.tabIndex === -1 && props?.ref && activeHooks) {
          props.ref.current = activeHooks.panel;
        }
        return { type, props, children };
      },
      useRef(initial) {
        return activeHooks.useRef(initial);
      },
      useEffect(effect, deps) {
        return activeHooks.useEffect(effect, deps);
      },
    };
    const sharedModalMod = loadTsModule("src/components/ModalDialog.tsx", {
      react: sharedReact,
    });

    function createMountedModal(id) {
      const refs = [];
      let hookIdx = 0;
      let prevDeps;
      let cleanup;
      let pendingEffects = [];
      const state = {
        panel: {
          id,
          focusCalls: 0,
          focus() {
            this.focusCalls += 1;
            fakeDocument.activeElement = this;
          },
          querySelectorAll() {
            return [];
          },
        },
        useRef(initial) {
          const idx = hookIdx++;
          if (!(idx in refs)) refs[idx] = { current: initial };
          return refs[idx];
        },
        useEffect(effect, deps) {
          const changed =
            prevDeps === undefined ||
            deps.length !== prevDeps.length ||
            deps.some((d, i) => !Object.is(d, prevDeps[i]));
          if (changed) {
            pendingEffects.push({ effect, deps });
          }
        },
      };
      return {
        panel: state.panel,
        render(isOpen, onClose) {
          hookIdx = 0;
          pendingEffects = [];
          activeHooks = state;
          const el = sharedModalMod.ModalDialog({
            isOpen,
            onClose,
            labelledBy: `${id}-title`,
            children: null,
          });
          if (el && el.props?.children?.props?.ref) {
            el.props.children.props.ref.current = state.panel;
          }
          activeHooks = null;
          // Flush useEffect after commit (matching React ref-attachment order)
          for (const item of pendingEffects) {
            if (typeof cleanup === "function") cleanup();
            cleanup = item.effect();
            prevDeps = item.deps;
          }
        },
        unmount() {
          if (typeof cleanup === "function") {
            cleanup();
            cleanup = undefined;
          }
        },
      };
    }

    const modal1 = createMountedModal("modal-1");
    const modal2 = createMountedModal("modal-2");
    let m1Closes = 0;
    let m2Closes = 0;

    // 1. Open modal 1 from pageTrigger; re-render with fresh inline onClose -> listener stays 1
    modal1.render(true, () => {
      m1Closes += 1;
    });
    assert.equal(fakeDocument.activeElement, modal1.panel);
    assert.equal(listeners.get("keydown")?.size, 1);
    assert.equal(sharedModalMod.openModalStack.length, 1);

    modal1.render(true, () => {
      m1Closes += 1;
    });
    assert.equal(listeners.get("keydown")?.size, 1);
    assert.equal(sharedModalMod.openModalStack.length, 1);

    // 2. Open modal 2 from wrappedNestedTrigger inside modal 1
    fakeDocument.activeElement = wrappedNestedTrigger;
    modal2.render(true, () => {
      m2Closes += 1;
    });
    assert.equal(fakeDocument.activeElement, modal2.panel);
    assert.equal(listeners.get("keydown")?.size, 2);
    assert.equal(sharedModalMod.openModalStack.length, 2);

    // 3. Escape only closes topmost modal 2
    const esc1 = createFakeKeyEvent("Escape");
    for (const fn of [...listeners.get("keydown")]) fn(esc1);
    assert.equal(m2Closes, 1);
    assert.equal(m1Closes, 0);
    assert.equal(esc1.defaultPrevented, true);

    // 4. Closing modal 2 restores focus to wrappedNestedTrigger and leaves modal 1 topmost
    modal2.render(false, () => {
      m2Closes += 1;
    });
    assert.equal(fakeDocument.activeElement, wrappedNestedTrigger);
    assert.equal(listeners.get("keydown")?.size, 1);
    assert.equal(sharedModalMod.openModalStack.length, 1);

    // 5. Next Escape closes modal 1
    const esc2 = createFakeKeyEvent("Escape");
    for (const fn of [...listeners.get("keydown")]) fn(esc2);
    assert.equal(m1Closes, 1);

    // 6. Closing modal 1 restores focus to original pageTrigger with zero leftover listeners
    modal1.render(false, () => {
      m1Closes += 1;
    });
    assert.equal(fakeDocument.activeElement, wrappedPageTrigger);
    assert.equal(listeners.get("keydown")?.size || 0, 0);
    assert.equal(sharedModalMod.openModalStack.length, 0);
  } finally {
    globalThis.document = prevDoc;
    globalThis.window = prevWin;
    globalThis.HTMLElement = prevHTMLElement;
  }
});
