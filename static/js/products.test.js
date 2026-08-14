"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const {lookupAction, projectedBalance} = require("./products.js");

test("lookup decisions accept only valid modal and search payloads", () => {
    assert.equal(lookupAction({result: "modal", url: "/inventory/products/1/receive/"}), "modal");
    assert.equal(lookupAction({result: "search", url: "/products/?q=tea"}), "search");
    assert.equal(lookupAction({result: "modal"}), "error");
    assert.equal(lookupAction({result: "ok", url: "/products/"}), "error");
});

test("projected balance handles signed whole numbers and ignores invalid input", () => {
    assert.equal(projectedBalance("5", "3"), 8);
    assert.equal(projectedBalance("5", "-8"), -3);
    assert.equal(projectedBalance("5", "1.5"), 5);
    assert.equal(projectedBalance("5", ""), 5);
});
