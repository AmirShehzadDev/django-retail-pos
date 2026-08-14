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

    const HEADER = "X-Product-Workspace";

    const projectedBalance = (current, rawChange) => {
        const currentNumber = Number.parseInt(current, 10);
        const value = String(rawChange ?? "").trim();
        if (!Number.isSafeInteger(currentNumber) || !/^[+-]?\d+$/.test(value)) {
            return currentNumber;
        }
        const change = Number(value);
        return Number.isSafeInteger(change) ? currentNumber + change : currentNumber;
    };

    const lookupAction = (payload) => {
        if (payload?.result === "modal" && typeof payload.url === "string") {
            return "modal";
        }
        if (payload?.result === "search" && typeof payload.url === "string") {
            return "search";
        }
        return "error";
    };

    const init = (document, window) => {
        const workspace = document.querySelector("[data-product-workspace]");
        if (!workspace || typeof window.fetch !== "function") {
            return;
        }
        const dialog = workspace.querySelector("[data-product-dialog]");
        const dialogContent = workspace.querySelector("[data-product-dialog-content]");
        const queryInput = workspace.querySelector("[data-product-query]");

        const announce = (message) => {
            if (!message) {
                return;
            }
            document.dispatchEvent(new window.CustomEvent("app:toast", {detail: {message}}));
        };

        const focusQuery = () => {
            if (!queryInput) {
                return;
            }
            queryInput.focus();
            if (typeof queryInput.select === "function") {
                queryInput.select();
            }
        };

        const parseJson = async (response) => {
            const contentType = response.headers.get("content-type") || "";
            if (!contentType.includes("application/json")) {
                throw new Error("The server returned an unexpected response.");
            }
            return response.json();
        };

        const initializeBalancePreview = (container) => {
            const preview = container.querySelector("[data-balance-preview]");
            const form = preview?.closest("form");
            const input = form?.querySelector("[data-quantity-change]");
            const warning = preview?.parentElement?.querySelector("[data-negative-warning]");
            if (!preview || !input) {
                return;
            }
            const update = () => {
                const projected = projectedBalance(preview.dataset.currentBalance, input.value);
                if (!Number.isSafeInteger(projected)) {
                    return;
                }
                preview.textContent = projected.toLocaleString("en-PK");
                preview.classList.toggle("text-red-800", projected < 0);
                preview.classList.toggle("text-slate-950", projected >= 0);
                if (warning) {
                    warning.hidden = projected >= 0;
                }
            };
            input.addEventListener("input", update);
            update();
        };

        const setDialogHtml = (html) => {
            dialogContent.innerHTML = html;
            initializeBalancePreview(dialogContent);
            if (!dialog.open) {
                dialog.showModal();
            }
            const target = dialogContent.querySelector("[data-autofocus], input:not([type='hidden']), select, textarea, button");
            target?.focus();
        };

        const openModal = async (url) => {
            try {
                const response = await window.fetch(url, {
                    headers: {[HEADER]: "modal"},
                    credentials: "same-origin",
                });
                const payload = await parseJson(response);
                if (payload.dialog_html) {
                    setDialogHtml(payload.dialog_html);
                    return;
                }
                announce(payload.message || "The product action could not be opened.");
            } catch (_error) {
                window.location.assign(url);
            }
        };

        const syncFilters = (url) => {
            const target = new window.URL(url, window.location.href);
            if (queryInput) {
                queryInput.value = target.searchParams.get("q") || "";
            }
            const form = workspace.querySelector("[data-product-filters]");
            if (!form) {
                return;
            }
            for (const element of form.elements) {
                if (!element.name) {
                    continue;
                }
                if (element.type === "checkbox") {
                    element.checked = target.searchParams.has(element.name);
                } else {
                    element.value = target.searchParams.get(element.name) || "";
                }
            }
        };

        const loadResults = async (url, {push = false} = {}) => {
            const response = await window.fetch(url, {
                headers: {[HEADER]: "results"},
                credentials: "same-origin",
            });
            if (!response.ok) {
                throw new Error("Products could not be refreshed.");
            }
            const html = await response.text();
            const results = workspace.querySelector("[data-product-results]");
            if (!results) {
                throw new Error("Products could not be refreshed.");
            }
            results.innerHTML = html;
            if (push) {
                window.history.pushState({}, "", url);
                syncFilters(url);
            }
        };

        workspace.addEventListener("click", (event) => {
            const closeButton = event.target.closest?.("[data-product-dialog-close]");
            if (closeButton) {
                event.preventDefault();
                dialog.close();
                focusQuery();
                return;
            }
            const modalLink = event.target.closest?.("[data-product-modal-url]");
            if (modalLink) {
                event.preventDefault();
                void openModal(modalLink.dataset.productModalUrl || modalLink.href);
                return;
            }
            const resultsLink = event.target.closest?.("[data-product-results-link]");
            if (resultsLink) {
                event.preventDefault();
                void loadResults(resultsLink.href, {push: true}).catch(() => window.location.assign(resultsLink.href));
            }
        });

        dialog.addEventListener("click", (event) => {
            if (event.target === dialog) {
                dialog.close();
                focusQuery();
            }
        });
        dialog.addEventListener("cancel", () => window.setTimeout(focusQuery, 0));

        workspace.addEventListener("submit", async (event) => {
            const form = event.target;
            if (form.matches("[data-product-lookup]")) {
                event.preventDefault();
                const url = new window.URL(form.action, window.location.href);
                url.search = new window.URLSearchParams(new window.FormData(form)).toString();
                try {
                    const response = await window.fetch(url, {
                        headers: {[HEADER]: "lookup"},
                        credentials: "same-origin",
                    });
                    const payload = await parseJson(response);
                    const action = lookupAction(payload);
                    if (action === "modal") {
                        await openModal(payload.url);
                    } else if (action === "search") {
                        await loadResults(payload.url, {push: true});
                    } else {
                        throw new Error(payload.message || "No product result was returned.");
                    }
                } catch (_error) {
                    window.location.assign(url);
                }
                return;
            }

            if (form.matches("[data-product-filters]")) {
                event.preventDefault();
                const url = new window.URL(form.action || window.location.pathname, window.location.href);
                url.search = new window.URLSearchParams(new window.FormData(form)).toString();
                void loadResults(url, {push: true}).catch(() => window.location.assign(url));
                return;
            }

            if (!form.matches("[data-product-modal-form]")) {
                return;
            }
            event.preventDefault();
            const submitButtons = form.querySelectorAll("button[type='submit']");
            submitButtons.forEach((button) => { button.disabled = true; });
            try {
                const response = await window.fetch(form.action, {
                    method: "POST",
                    body: new window.FormData(form),
                    headers: {[HEADER]: "modal"},
                    credentials: "same-origin",
                });
                const payload = await parseJson(response);
                if (payload.dialog_html) {
                    setDialogHtml(payload.dialog_html);
                    return;
                }
                if (response.ok && payload.result === "ok") {
                    dialog.close();
                    announce(payload.message);
                    try {
                        await loadResults(window.location.href);
                    } catch (_error) {
                        announce("The change was saved. Refresh the page to update the product list.");
                    }
                    focusQuery();
                    return;
                }
                throw new Error(payload.message || "The product action could not be completed.");
            } catch (error) {
                announce(error.message || "The product action could not be completed.");
            } finally {
                submitButtons.forEach((button) => { button.disabled = false; });
            }
        });

        window.addEventListener("popstate", () => {
            void loadResults(window.location.href).then(() => syncFilters(window.location.href)).catch(() => {});
        });
    };

    return {init, lookupAction, projectedBalance};
});
