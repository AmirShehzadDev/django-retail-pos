(function (root, factory) {
    "use strict";

    const api = factory();
    if (typeof module === "object" && module.exports) {
        module.exports = api;
    }
    if (root.document) {
        api.init(root.document, root);
    }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
    "use strict";

    function nonnegativeInteger(value) {
        const normalized = String(value ?? "").trim();
        if (!/^\d+$/.test(normalized)) {
            return null;
        }
        return BigInt(normalized);
    }

    function calculateRefundMinorUnits(entries) {
        let total = 0n;
        for (const entry of entries) {
            const quantity = nonnegativeInteger(entry.quantity);
            const unitMinor = nonnegativeInteger(entry.unitMinor);
            if (quantity !== null && unitMinor !== null) {
                total += quantity * unitMinor;
            }
        }
        return total;
    }

    function formatMinorUnits(minorUnits) {
        const negative = minorUnits < 0n;
        const absolute = negative ? -minorUnits : minorUnits;
        const rupees = absolute / 100n;
        const paisa = (absolute % 100n).toString().padStart(2, "0");
        return `${negative ? "-" : ""}${rupees}.${paisa}`;
    }

    function init(document, window) {
        const dialog = document.querySelector("[data-correction-dialog]");
        const csrf = () =>
            document.cookie
                .split("; ")
                .find((row) => row.startsWith("csrftoken="))
                ?.split("=")[1] || "";

        function updateRefund(root = document) {
            const entries = Array.from(root.querySelectorAll("[data-return-line]"), (line) => ({
                quantity: line.querySelector("[data-return-quantity]")?.value || "0",
                unitMinor: line.dataset.unitMinor || "0",
            }));
            const output = root.querySelector("[data-refund-total]");
            if (output) {
                output.textContent = formatMinorUnits(calculateRefundMinorUnits(entries));
            }
        }

        async function submitEnhanced(event) {
            if (!dialog || !dialog.open) {
                return;
            }
            event.preventDefault();
            const form = event.currentTarget;
            const total = form.querySelector("[data-refund-total]")?.textContent;
            const question =
                form.dataset.kind === "void"
                    ? "Confirm this full void and cash refund?"
                    : `Complete this return and refund PKR ${total}?`;
            if (!window.confirm(question)) {
                return;
            }
            const response = await window.fetch(form.action, {
                method: "POST",
                body: new window.FormData(form),
                headers: {"X-Order-Correction": "modal", "X-CSRFToken": csrf()},
            });
            const data = await response.json();
            if (response.status === 422) {
                dialog.innerHTML = data.dialog_html;
                wire(dialog);
                return;
            }
            if (!response.ok) {
                window.alert("The correction could not be completed. Reload and try again.");
                return;
            }
            dialog.close();
            const detail = await window.fetch(data.detail_url, {
                headers: {"X-Order-Correction": "detail"},
            });
            if (detail.ok) {
                document.querySelector("[data-order-detail]").innerHTML = await detail.text();
            }
            document.dispatchEvent(
                new window.CustomEvent("app:toast", {
                    detail: {message: data.message, level: "success"},
                }),
            );
        }

        function wire(root) {
            root.querySelectorAll("[data-dialog-close]").forEach((button) =>
                button.addEventListener("click", () => dialog?.close()),
            );
            root.querySelector("[data-return-all]")?.addEventListener("click", () => {
                root.querySelectorAll("[data-return-line]").forEach((line) => {
                    const input = line.querySelector("[data-return-quantity]");
                    if (input) {
                        input.value = line.dataset.remaining;
                    }
                });
                updateRefund(root);
            });
            root.querySelectorAll("[data-disposition-all]").forEach((button) =>
                button.addEventListener("click", () => {
                    root.querySelectorAll("[data-return-line]").forEach((line) => {
                        const quantity = line.querySelector("[data-return-quantity]");
                        const disposition = line.querySelector("[data-return-disposition]");
                        if (Number(quantity?.value) > 0 && disposition) {
                            disposition.value = button.dataset.dispositionAll;
                        }
                    });
                }),
            );
            root.querySelectorAll("[data-return-quantity]").forEach((input) =>
                input.addEventListener("input", () => updateRefund(root)),
            );
            root.querySelector("[data-correction-form]")?.addEventListener(
                "submit",
                submitEnhanced,
            );
            updateRefund(root);
        }

        document.addEventListener("click", async (event) => {
            const link = event.target.closest("[data-correction-url]");
            if (!link || !dialog) {
                return;
            }
            event.preventDefault();
            const response = await window.fetch(link.href, {
                headers: {"X-Order-Correction": "modal"},
            });
            if (!response.ok) {
                window.location.assign(link.href);
                return;
            }
            dialog.innerHTML = (await response.json()).dialog_html;
            wire(dialog);
            dialog.showModal();
        });
        wire(document);
    }

    return {
        calculateRefundMinorUnits,
        formatMinorUnits,
        init,
    };
});
