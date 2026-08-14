(() => {
    "use strict";

    document.documentElement.classList.add("js-ready");

    const dismissToast = (toast, immediate = false) => {
        if (toast.dataset.toastClosing === "true") {
            return;
        }
        toast.dataset.toastClosing = "true";
        if (immediate) {
            toast.hidden = true;
            toast.remove();
            return;
        }
        toast.classList.add("translate-x-4", "opacity-0");
        window.setTimeout(() => toast.remove(), 200);
    };

    const initializeToast = (toast) => {
        if (toast.dataset.toastInitialized === "true") {
            return;
        }
        toast.dataset.toastInitialized = "true";
        const closeButton = toast.querySelector("[data-toast-dismiss]");
        const configuredTimeout = Number.parseInt(toast.dataset.toastTimeout || "", 10);
        let remaining = Number.isSafeInteger(configuredTimeout) ? configuredTimeout : 0;
        let deadline = 0;
        let timer = null;

        const pauseTimer = () => {
            if (timer === null) {
                return;
            }
            window.clearTimeout(timer);
            timer = null;
            remaining = Math.max(0, deadline - Date.now());
        };

        const startTimer = () => {
            if (remaining <= 0 || toast.dataset.toastClosing === "true") {
                return;
            }
            deadline = Date.now() + remaining;
            timer = window.setTimeout(() => {
                timer = null;
                dismissToast(toast);
            }, remaining);
        };

        if (closeButton) {
            closeButton.addEventListener("click", () => {
                pauseTimer();
                dismissToast(toast, true);
            });
        }
        toast.addEventListener("mouseenter", pauseTimer);
        toast.addEventListener("mouseleave", startTimer);
        toast.addEventListener("focusin", pauseTimer);
        toast.addEventListener("focusout", (event) => {
            if (!toast.contains(event.relatedTarget)) {
                startTimer();
            }
        });
        startTimer();
    };

    document.addEventListener("click", (event) => {
        const dismissButton = event.target?.closest?.("[data-toast-dismiss]");
        const toast = dismissButton?.closest("[data-toast]");
        if (!toast) {
            return;
        }
        event.preventDefault();
        dismissToast(toast, true);
    }, true);

    document.addEventListener("app:toast", (event) => {
        const message = typeof event.detail?.message === "string" ? event.detail.message.trim() : "";
        const stack = document.querySelector("[data-toast-stack]");
        if (!message || !stack) {
            return;
        }
        const requestedTimeout = Number.parseInt(event.detail?.timeout, 10);
        const timeout = Number.isSafeInteger(requestedTimeout)
            ? Math.min(30000, Math.max(1000, requestedTimeout))
            : 5000;
        const toast = document.createElement("div");
        toast.className = "pointer-events-auto flex items-start gap-3 rounded-xl border border-emerald-300 bg-emerald-50 p-4 text-sm font-semibold text-emerald-950 shadow-xl transition duration-200 motion-reduce:transition-none";
        toast.setAttribute("role", "status");
        toast.dataset.toast = "";
        toast.dataset.toastTimeout = String(timeout);

        const text = document.createElement("p");
        text.className = "min-w-0 flex-1";
        text.textContent = message;
        const closeButton = document.createElement("button");
        closeButton.type = "button";
        closeButton.className = "pointer-events-auto -m-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-xl font-black text-emerald-900 hover:bg-emerald-100 focus-visible:outline-3 focus-visible:outline-offset-1 focus-visible:outline-emerald-700";
        closeButton.setAttribute("aria-label", "Dismiss notification");
        closeButton.dataset.toastDismiss = "";
        closeButton.textContent = "×";
        toast.append(text, closeButton);
        stack.prepend(toast);
        initializeToast(toast);
    });

    for (const toast of document.querySelectorAll("[data-toast]")) {
        initializeToast(toast);
    }

    const autofocusTarget = document.querySelector("[data-autofocus]");
    if (autofocusTarget) {
        autofocusTarget.focus();
        if (typeof autofocusTarget.select === "function") {
            autofocusTarget.select();
        }
    }

    for (const form of document.querySelectorAll("form[data-disable-on-submit]")) {
        form.addEventListener("submit", () => {
            for (const button of form.querySelectorAll("button[type='submit']")) {
                button.disabled = true;
                button.setAttribute("aria-disabled", "true");
            }
        });
    }

    for (const preview of document.querySelectorAll("[data-balance-preview]")) {
        const form = preview.closest("form");
        const input = form ? form.querySelector("[data-quantity-change]") : null;
        const warning = preview.parentElement.querySelector("[data-negative-warning]");
        const currentBalance = Number.parseInt(preview.dataset.currentBalance, 10);
        if (!input || !Number.isSafeInteger(currentBalance)) {
            continue;
        }

        const updatePreview = () => {
            const rawChange = input.value.trim();
            const change = /^[+-]?\d+$/.test(rawChange) ? Number(rawChange) : Number.NaN;
            const projected = Number.isSafeInteger(change) ? currentBalance + change : currentBalance;
            preview.textContent = projected.toLocaleString("en-PK");
            preview.dataset.negative = projected < 0 ? "true" : "false";
            preview.classList.toggle("text-red-800", projected < 0);
            preview.classList.toggle("text-slate-950", projected >= 0);
            if (warning) {
                warning.hidden = projected >= 0;
            }
        };
        input.addEventListener("input", updatePreview);
        updatePreview();
    }
})();
