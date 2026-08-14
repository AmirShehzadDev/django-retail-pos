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

    class ScannerQueue {
        constructor(send, initialVersion) {
            this.send = send;
            this.version = typeof initialVersion === "string" ? initialVersion : "";
            this.pending = [];
            this.running = false;
            this.idleWaiters = [];
        }

        enqueue(barcode) {
            this.pending.push(String(barcode));
            if (!this.running) {
                void this.drain();
            }
        }

        clear() {
            this.pending.length = 0;
        }

        setVersion(version) {
            if (typeof version === "string") {
                this.version = version;
            }
        }

        whenIdle() {
            if (!this.running && this.pending.length === 0) {
                return Promise.resolve();
            }
            return new Promise((resolve) => this.idleWaiters.push(resolve));
        }

        async drain() {
            if (this.running) {
                return;
            }
            this.running = true;
            try {
                while (this.pending.length > 0) {
                    const barcode = this.pending.shift();
                    let outcome;
                    try {
                        outcome = await this.send(barcode, this.version);
                    } catch (_error) {
                        this.clear();
                        break;
                    }
                    if (outcome && typeof outcome.version === "string") {
                        this.version = outcome.version;
                    }
                    if (!outcome || outcome.stop) {
                        this.clear();
                        break;
                    }
                }
            } finally {
                this.running = false;
                const waiters = this.idleWaiters.splice(0);
                for (const resolve of waiters) {
                    resolve();
                }
            }
        }
    }

    function parseMoneyToMinorUnits(value) {
        const normalized = String(value || "").trim();
        const match = normalized.match(/^(\d+)(?:\.(\d{0,2}))?$/);
        if (!match) {
            return null;
        }
        return (BigInt(match[1]) * 100n) + BigInt((match[2] || "").padEnd(2, "0"));
    }

    function formatSignedMoney(minorUnits) {
        const negative = minorUnits < 0n;
        const absolute = negative ? -minorUnits : minorUnits;
        const whole = absolute / 100n;
        const fraction = String(absolute % 100n).padStart(2, "0");
        return "PKR " + (negative ? "-" : "") + whole + "." + fraction;
    }

    function formatCompletionMessage(completion) {
        if (!completion || typeof completion !== "object") {
            return "";
        }
        const orderNumber = typeof completion.order_number === "string"
            ? completion.order_number.trim()
            : "";
        const total = typeof completion.total === "string" ? completion.total.trim() : "";
        const change = typeof completion.change === "string" ? completion.change.trim() : "";
        if (!orderNumber || !total || !change) {
            return "";
        }
        const signedChange = change.startsWith("-") || /^0(?:\.0{1,2})?$/.test(change)
            ? change
            : "+" + change;
        const action = completion.already_completed ? "was already completed" : "completed";
        return orderNumber + " " + action + ". Total PKR " + total + ". Change PKR " + signedChange + ".";
    }

    function clearDialogKeyAction(key, cancelFocused) {
        if (key === "Escape") {
            return "cancel";
        }
        if (key === "Enter" && !cancelFocused) {
            return "confirm";
        }
        return "";
    }

    function checkoutShortcutAction(key, shiftKey, hasModifier, scannerFocused, triggerEnabled) {
        if (
            key === "Tab" &&
            !shiftKey &&
            !hasModifier &&
            scannerFocused &&
            triggerEnabled
        ) {
            return "focus-checkout";
        }
        return "";
    }

    function checkoutDialogKeyAction(key, shiftKey, cashFocused) {
        if (key === "Escape") {
            return "cancel";
        }
        if (key === "Tab" && !shiftKey && cashFocused) {
            return "focus-complete";
        }
        return "";
    }

    function init(document, window) {
        const workspace = document.querySelector("[data-pos-workspace]");
        if (!workspace) {
            return;
        }

        let currentVersion = workspace.dataset.posVersion || "";
        let initialStartSubmitted = false;
        const status = workspace.querySelector("[data-pos-status]");

        function updateChangePreview() {
            const form = workspace.querySelector("[data-pos-checkout]");
            if (!form) {
                return;
            }
            const output = form.querySelector("[data-pos-change]");
            const input = form.querySelector("[name='cash_received']");
            const total = parseMoneyToMinorUnits(form.dataset.posTotal);
            const received = input ? parseMoneyToMinorUnits(input.value) : null;
            if (!output || total === null || received === null) {
                if (output) {
                    output.textContent = "PKR --";
                    output.classList.remove("text-emerald-300", "text-red-300");
                }
                return;
            }
            const change = received - total;
            output.textContent = formatSignedMoney(change);
            output.classList.toggle("text-emerald-300", change > 0n);
            output.classList.toggle("text-red-300", change < 0n);
        }

        function announce(message, isError) {
            if (!status) {
                return;
            }
            status.textContent = "";
            window.setTimeout(function () {
                status.textContent = message;
                if (isError) {
                    status.focus();
                }
            }, 0);
        }

        function activeControlNeedsFocus() {
            const active = document.activeElement;
            if (!active || active === document.body) {
                return false;
            }
            if (active.matches("[data-pos-scanner]")) {
                return false;
            }
            return active.matches("input, textarea, select, button, a, [contenteditable='true']");
        }

        function focusScanner(force) {
            if (!force && activeControlNeedsFocus()) {
                return;
            }
            const scanner = workspace.querySelector("[data-pos-scanner]");
            if (!scanner || scanner.disabled) {
                return;
            }
            scanner.focus();
            if (typeof scanner.select === "function") {
                scanner.select();
            }
        }

        function openCheckoutDialog() {
            const dialog = workspace.querySelector("[data-pos-checkout-dialog]");
            if (!dialog || typeof dialog.showModal !== "function") {
                return false;
            }
            if (!dialog.open) {
                dialog.showModal();
            }
            updateChangePreview();
            window.setTimeout(function () {
                const input = dialog.querySelector("[data-pos-cash-received]");
                if (!input) {
                    return;
                }
                input.focus();
                if (typeof input.select === "function") {
                    input.select();
                }
            }, 0);
            return true;
        }

        function closeCheckoutDialog(dialog) {
            if (dialog && dialog.open && typeof dialog.close === "function") {
                dialog.close();
            }
            window.setTimeout(function () { focusScanner(true); }, 0);
        }

        function requireProtocolString(payload, key, allowEmpty) {
            const value = payload[key];
            if (typeof value !== "string" || (!allowEmpty && !/^\d+$/.test(value))) {
                throw new Error("The POS returned an invalid " + key + ".");
            }
            return value;
        }

        function replaceFragment(selector, html) {
            if (typeof html !== "string") {
                throw new Error("The POS response did not include the current order view.");
            }
            const template = document.createElement("template");
            template.innerHTML = html.trim();
            const replacement = template.content.firstElementChild;
            const current = workspace.querySelector(selector);
            if (!replacement || !current) {
                throw new Error("The POS response could not be displayed safely.");
            }
            current.replaceWith(replacement);
        }

        function applyState(payload) {
            const draftId = requireProtocolString(payload, "draft_id", true);
            const version = requireProtocolString(payload, "version", true);
            if (typeof payload.can_create_draft !== "boolean") {
                throw new Error("The POS returned an invalid order-tab state.");
            }
            replaceFragment("[data-pos-tabs]", payload.tabs_html);
            replaceFragment("[data-pos-panel]", payload.draft_panel_html);
            currentVersion = version;
            workspace.dataset.posVersion = version;
            queue.setVersion(version);
            updateChangePreview();

            const newDraftForm = workspace.querySelector("[data-pos-new-draft]");
            if (newDraftForm) {
                newDraftForm.hidden = !payload.can_create_draft;
            }

            const url = new window.URL(window.location.href);
            url.searchParams.delete("q");
            if (draftId) {
                url.searchParams.set("draft", draftId);
            } else {
                url.searchParams.delete("draft");
            }
            window.history.replaceState({}, "", url.toString());
        }

        async function request(form, formData) {
            const csrf = formData.get("csrfmiddlewaretoken");
            const headers = {"X-POS-Enhanced": "1", "Accept": "application/json"};
            if (typeof csrf === "string" && csrf) {
                headers["X-CSRFToken"] = csrf;
            }
            const response = await window.fetch(form.action, {
                method: "POST",
                body: formData,
                headers: headers,
                credentials: "same-origin",
                redirect: "follow",
            });
            const contentType = response.headers.get("content-type") || "";
            if (!contentType.includes("application/json")) {
                throw new Error("The POS returned an unexpected response. Refresh before retrying.");
            }
            return {response: response, payload: await response.json()};
        }

        async function sendScan(barcode, version) {
            const form = workspace.querySelector("[data-pos-scan-form]");
            if (!form) {
                announce("The scanner is unavailable. Refresh before retrying.", true);
                return {stop: true};
            }
            const formData = new window.FormData(form);
            formData.set("barcode", barcode);
            formData.set("expected_version", version);

            try {
                const result = await request(form, formData);
                const payload = result.payload;
                requireProtocolString(payload, "draft_id", false);
                requireProtocolString(payload, "version", false);

                if (result.response.ok && payload.result === "quick_create_required") {
                    if (typeof payload.next_url !== "string" || !payload.next_url) {
                        throw new Error("The quick-create destination is unavailable.");
                    }
                    announce("Unknown barcode. Opening quick-create; later scans were cleared.", false);
                    window.location.assign(payload.next_url);
                    return {version: payload.version, stop: true};
                }

                if (typeof payload.tabs_html === "string" && typeof payload.draft_panel_html === "string") {
                    applyState(payload);
                }
                if (!result.response.ok || payload.result !== "ok") {
                    announce(payload.error || "The scan was not applied. Review the current order and retry.", true);
                    return {version: payload.version, stop: true};
                }

                announce(form.dataset.posSuccess || "Product added.", false);
                window.setTimeout(function () { focusScanner(false); }, 0);
                return {version: payload.version, stop: false};
            } catch (error) {
                announce(error.message || "The scan could not be sent. Refresh before retrying.", true);
                return {stop: true};
            }
        }

        const queue = new ScannerQueue(sendScan, currentVersion);

        async function submitMutation(form) {
            const isCheckout = form.matches("[data-pos-checkout]");
            const buttons = form.querySelectorAll("button[type='submit']");
            function enableButtons() {
                for (const button of buttons) {
                    button.disabled = false;
                    button.removeAttribute("aria-disabled");
                }
            }
            for (const button of buttons) {
                button.disabled = true;
                button.setAttribute("aria-disabled", "true");
            }
            const formData = new window.FormData(form);
            if (formData.has("expected_version")) {
                formData.set("expected_version", currentVersion);
            }
            try {
                const result = await request(form, formData);
                const payload = result.payload;
                if (typeof payload.tabs_html === "string" && typeof payload.draft_panel_html === "string") {
                    applyState(payload);
                }
                if (!result.response.ok || payload.result !== "ok") {
                    queue.clear();
                    announce(payload.error || "The order was not changed. Review it before retrying.", true);
                    enableButtons();
                    if (isCheckout && payload.result === "invalid") {
                        window.setTimeout(function () { openCheckoutDialog(); }, 1);
                    }
                    return;
                }
                enableButtons();
                const completionMessage = formatCompletionMessage(payload.completed_order);
                const successMessage = completionMessage || form.dataset.posSuccess || "Order updated.";
                if (completionMessage || form.hasAttribute("data-pos-toast-success")) {
                    document.dispatchEvent(new window.CustomEvent("app:toast", {
                        detail: {message: successMessage, timeout: 5000},
                    }));
                }
                announce(successMessage, false);
                window.setTimeout(function () { focusScanner(false); }, 0);
            } catch (error) {
                queue.clear();
                announce(error.message || "The request failed. Refresh before retrying.", true);
                enableButtons();
            }
        }

        workspace.addEventListener("submit", function (event) {
            const form = event.target.closest("form");
            if (!form || (!form.matches("[data-pos-mutation]") && !form.matches("[data-pos-initial-start]"))) {
                return;
            }
            event.preventDefault();
            if (form.matches("[data-pos-scan-form]")) {
                const input = form.querySelector("[data-pos-scanner]");
                if (!input) {
                    return;
                }
                const barcode = input.value;
                input.value = "";
                queue.enqueue(barcode);
                return;
            }
            void submitMutation(form);
        });

        workspace.addEventListener("input", function (event) {
            if (event.target.matches("[data-pos-checkout] [name='cash_received']")) {
                updateChangePreview();
            }
        });

        workspace.addEventListener("click", function (event) {
            const checkoutTrigger = event.target.closest("[data-pos-checkout-trigger]");
            if (checkoutTrigger && !checkoutTrigger.disabled) {
                event.preventDefault();
                openCheckoutDialog();
                return;
            }

            const checkoutCancel = event.target.closest("[data-pos-checkout-cancel]");
            if (checkoutCancel) {
                event.preventDefault();
                closeCheckoutDialog(checkoutCancel.closest("[data-pos-checkout-dialog]"));
                return;
            }

            const trigger = event.target.closest("[data-pos-clear-trigger]");
            if (trigger) {
                const dialog = workspace.querySelector("[data-pos-clear-dialog]");
                if (dialog && typeof dialog.showModal === "function") {
                    event.preventDefault();
                    dialog.showModal();
                    const confirm = dialog.querySelector("[data-pos-clear-confirm]");
                    if (confirm) {
                        confirm.focus();
                    }
                }
                return;
            }

            const cancel = event.target.closest("[data-pos-clear-cancel]");
            if (!cancel) {
                return;
            }
            const dialog = cancel.closest("[data-pos-clear-dialog]");
            if (dialog && typeof dialog.close === "function") {
                event.preventDefault();
                dialog.close();
                window.setTimeout(function () { focusScanner(true); }, 0);
            }
        });

        document.addEventListener("keydown", function (event) {
            if (event.defaultPrevented) {
                return;
            }
            const checkoutDialog = workspace.querySelector("[data-pos-checkout-dialog][open]");
            if (checkoutDialog) {
                const cashFocused = Boolean(
                    document.activeElement &&
                    document.activeElement.matches("[data-pos-cash-received]")
                );
                const action = checkoutDialogKeyAction(event.key, event.shiftKey, cashFocused);
                if (action === "cancel") {
                    event.preventDefault();
                    closeCheckoutDialog(checkoutDialog);
                } else if (action === "focus-complete") {
                    const complete = checkoutDialog.querySelector("[data-pos-checkout-confirm]");
                    if (complete && !complete.disabled) {
                        event.preventDefault();
                        complete.focus();
                    }
                }
                return;
            }
            if (event.ctrlKey || event.metaKey || event.altKey) {
                return;
            }
            const dialog = workspace.querySelector("[data-pos-clear-dialog][open]");
            if (dialog) {
                const cancelFocused = Boolean(
                    document.activeElement &&
                    document.activeElement.matches("[data-pos-clear-cancel]")
                );
                const action = clearDialogKeyAction(event.key, cancelFocused);
                if (action === "cancel") {
                    event.preventDefault();
                    dialog.close();
                    window.setTimeout(function () { focusScanner(true); }, 0);
                } else if (action === "confirm") {
                    event.preventDefault();
                    const form = dialog.querySelector("[data-pos-clear-form]");
                    const confirm = dialog.querySelector("[data-pos-clear-confirm]");
                    if (form && typeof form.requestSubmit === "function") {
                        form.requestSubmit(confirm || undefined);
                    } else if (confirm) {
                        confirm.click();
                    }
                }
                return;
            }
            const target = event.target;
            const checkoutTrigger = workspace.querySelector("[data-pos-checkout-trigger]");
            const shortcutAction = checkoutShortcutAction(
                event.key,
                event.shiftKey,
                event.ctrlKey || event.metaKey || event.altKey,
                Boolean(target && target.matches("[data-pos-scanner]")),
                Boolean(checkoutTrigger && !checkoutTrigger.disabled)
            );
            if (shortcutAction === "focus-checkout") {
                event.preventDefault();
                checkoutTrigger.focus();
                return;
            }
            if (target && target.matches("input, textarea, select, button, a, [contenteditable='true']")) {
                return;
            }
            if (event.key.length === 1) {
                focusScanner(true);
            }
        });

        updateChangePreview();
        focusScanner(false);
        const initialStart = workspace.querySelector("[data-pos-initial-start]");
        if (initialStart && !initialStartSubmitted) {
            initialStartSubmitted = true;
            void submitMutation(initialStart);
        }
    }

    return {
        ScannerQueue: ScannerQueue,
        parseMoneyToMinorUnits: parseMoneyToMinorUnits,
        formatSignedMoney: formatSignedMoney,
        formatCompletionMessage: formatCompletionMessage,
        clearDialogKeyAction: clearDialogKeyAction,
        checkoutShortcutAction: checkoutShortcutAction,
        checkoutDialogKeyAction: checkoutDialogKeyAction,
        init: init,
    };
});
