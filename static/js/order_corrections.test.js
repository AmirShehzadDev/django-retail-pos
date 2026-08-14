"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const {
    calculateRefundMinorUnits,
    formatMinorUnits,
} = require("./order_corrections.js");

test("refund follows each selected quantity and original unit price", () => {
    const total = calculateRefundMinorUnits([
        {quantity: "2", unitMinor: "3000"},
        {quantity: "1", unitMinor: "1999"},
        {quantity: "0", unitMinor: "50000"},
    ]);

    assert.equal(total, 7999n);
    assert.equal(formatMinorUnits(total), "79.99");
});

test("refund calculation remains exact for large whole quantities", () => {
    const total = calculateRefundMinorUnits([
        {quantity: "9007199254740993", unitMinor: "1234"},
    ]);

    assert.equal(total, 11114883880350385362n);
    assert.equal(formatMinorUnits(total), "111148838803503853.62");
});

test("invalid preview values do not contribute to the refund", () => {
    const total = calculateRefundMinorUnits([
        {quantity: "1.5", unitMinor: "1000"},
        {quantity: "2", unitMinor: "invalid"},
        {quantity: "3", unitMinor: "250"},
    ]);

    assert.equal(total, 750n);
});
