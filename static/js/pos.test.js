"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const {
    ScannerQueue,
    checkoutDialogKeyAction,
    checkoutShortcutAction,
    clearDialogKeyAction,
    formatCompletionMessage,
    formatSignedMoney,
    parseMoneyToMinorUnits,
} = require("./pos.js");

test("scanner Tab shortcut is narrow and requires an enabled checkout", () => {
    assert.equal(checkoutShortcutAction("Tab", false, false, true, true), "focus-checkout");
    assert.equal(checkoutShortcutAction("Tab", true, false, true, true), "");
    assert.equal(checkoutShortcutAction("Tab", false, true, true, true), "");
    assert.equal(checkoutShortcutAction("Tab", false, false, false, true), "");
    assert.equal(checkoutShortcutAction("Tab", false, false, true, false), "");
    assert.equal(checkoutShortcutAction("Enter", false, false, true, true), "");
});

test("checkout dialog keyboard moves from cash to completion and Escape cancels", () => {
    assert.equal(checkoutDialogKeyAction("Tab", false, true), "focus-complete");
    assert.equal(checkoutDialogKeyAction("Tab", true, true), "");
    assert.equal(checkoutDialogKeyAction("Tab", false, false), "");
    assert.equal(checkoutDialogKeyAction("Escape", false, false), "cancel");
    assert.equal(checkoutDialogKeyAction("Enter", false, true), "");
});

test("clear dialog keyboard choices keep Escape safe and Enter explicit", () => {
    assert.equal(clearDialogKeyAction("Enter", false), "confirm");
    assert.equal(clearDialogKeyAction("Enter", true), "");
    assert.equal(clearDialogKeyAction("Escape", false), "cancel");
    assert.equal(clearDialogKeyAction(" ", false), "");
});

test("cash values use exact minor units and signed change formatting", () => {
    assert.equal(parseMoneyToMinorUnits("100"), 10000n);
    assert.equal(parseMoneyToMinorUnits("99.5"), 9950n);
    assert.equal(parseMoneyToMinorUnits("99.999"), null);
    assert.equal(formatSignedMoney(100n), "PKR 1.00");
    assert.equal(formatSignedMoney(-100n), "PKR -1.00");
    assert.equal(formatSignedMoney(0n), "PKR 0.00");
});

test("completion messages include order total and signed change", () => {
    assert.equal(
        formatCompletionMessage({
            order_number: "ORD-000123",
            total: "99.00",
            change: "1.00",
            already_completed: false,
        }),
        "ORD-000123 completed. Total PKR 99.00. Change PKR +1.00.",
    );
    assert.equal(
        formatCompletionMessage({
            order_number: "ORD-000123",
            total: "99.00",
            change: "-1.00",
            already_completed: true,
        }),
        "ORD-000123 was already completed. Total PKR 99.00. Change PKR -1.00.",
    );
    assert.equal(formatCompletionMessage({order_number: "ORD-1"}), "");
});

test("scanner requests run FIFO with opaque returned versions", async () => {
    const calls = [];
    const returned = ["9007199254740993", "9007199254740994", "9007199254740995"];
    const queue = new ScannerQueue(async (barcode, version) => {
        calls.push([barcode, version]);
        return {version: returned[calls.length - 1], stop: false};
    }, "9007199254740992");

    queue.enqueue("001");
    queue.enqueue("002");
    queue.enqueue("003");
    await queue.whenIdle();

    assert.deepEqual(calls, [
        ["001", "9007199254740992"],
        ["002", "9007199254740993"],
        ["003", "9007199254740994"],
    ]);
    assert.equal(queue.version, "9007199254740995");
});

test("a conflict stops and clears later scans", async () => {
    const calls = [];
    const queue = new ScannerQueue(async (barcode, version) => {
        calls.push([barcode, version]);
        return {version: "42", stop: true};
    }, "41");

    queue.enqueue("first");
    queue.enqueue("must-not-run");
    await queue.whenIdle();

    assert.deepEqual(calls, [["first", "41"]]);
    assert.equal(queue.pending.length, 0);
});

test("an unknown-scan boundary stops later queued values without numeric coercion", async () => {
    const calls = [];
    const queue = new ScannerQueue(async (barcode, version) => {
        calls.push([barcode, version]);
        return {version: "18446744073709551615", stop: true};
    }, "18446744073709551614");

    queue.enqueue("unknown");
    queue.enqueue("rescan-this-later");
    await queue.whenIdle();

    assert.deepEqual(calls, [["unknown", "18446744073709551614"]]);
    assert.equal(queue.version, "18446744073709551615");
});

test("a rejected request is never retried", async () => {
    let attempts = 0;
    const queue = new ScannerQueue(async () => {
        attempts += 1;
        throw new Error("network loss");
    }, "7");

    queue.enqueue("one-attempt-only");
    await queue.whenIdle();

    assert.equal(attempts, 1);
    assert.equal(queue.pending.length, 0);
});
