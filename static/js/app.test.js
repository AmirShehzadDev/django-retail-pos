"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");

test("toast close control removes the notification immediately", () => {
    let clickHandler = null;
    const previousDocument = global.document;
    global.document = {
        documentElement: {classList: {add() {}}},
        addEventListener(type, handler, capture) {
            if (type === "click" && capture === true) {
                clickHandler = handler;
            }
        },
        querySelector() {
            return null;
        },
        querySelectorAll() {
            return [];
        },
    };

    const modulePath = require.resolve("./app.js");
    delete require.cache[modulePath];
    require(modulePath);

    let removed = false;
    let prevented = false;
    const toast = {
        dataset: {},
        hidden: false,
        remove() {
            removed = true;
        },
    };
    const button = {
        closest(selector) {
            return selector === "[data-toast]" ? toast : null;
        },
    };
    const target = {
        closest(selector) {
            return selector === "[data-toast-dismiss]" ? button : null;
        },
    };

    try {
        assert.equal(typeof clickHandler, "function");
        clickHandler({
            target,
            preventDefault() {
                prevented = true;
            },
        });

        assert.equal(prevented, true);
        assert.equal(toast.hidden, true);
        assert.equal(toast.dataset.toastClosing, "true");
        assert.equal(removed, true);
    } finally {
        delete require.cache[modulePath];
        global.document = previousDocument;
    }
});

test("dynamic toast treats the completion message as text and initializes dismissal", () => {
    const listeners = new Map();
    const previousDocument = global.document;
    const previousWindow = global.window;
    const stack = {
        first: null,
        prepend(node) {
            this.first = node;
        },
    };
    const createElement = (tagName) => ({
        tagName,
        dataset: {},
        children: [],
        classList: {add() {}},
        addEventListener() {},
        append(...children) {
            this.children.push(...children);
        },
        contains() {
            return false;
        },
        querySelector(selector) {
            return selector === "[data-toast-dismiss]" ? this.children[1] || null : null;
        },
        remove() {},
        setAttribute(name, value) {
            this[name] = value;
        },
    });
    global.window = {
        clearTimeout() {},
        setTimeout() {
            return 1;
        },
    };
    global.document = {
        documentElement: {classList: {add() {}}},
        addEventListener(type, handler) {
            listeners.set(type, handler);
        },
        createElement,
        querySelector(selector) {
            return selector === "[data-toast-stack]" ? stack : null;
        },
        querySelectorAll() {
            return [];
        },
    };

    const modulePath = require.resolve("./app.js");
    delete require.cache[modulePath];
    require(modulePath);

    try {
        listeners.get("app:toast")({
            detail: {message: "<img src=x onerror=alert(1)>", timeout: 5000},
        });

        assert.equal(stack.first.children[0].textContent, "<img src=x onerror=alert(1)>");
        assert.equal(stack.first.dataset.toastInitialized, "true");
        assert.equal(stack.first.children[1].textContent, "×");
    } finally {
        delete require.cache[modulePath];
        global.document = previousDocument;
        global.window = previousWindow;
    }
});
