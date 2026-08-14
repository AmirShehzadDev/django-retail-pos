class TerminalUnavailable(Exception):
    """The trusted POS terminal configuration cannot be used safely."""


class DraftLimitReached(Exception):
    """The resolved terminal already has all three active draft slots."""


class DraftVersionConflict(Exception):
    def __init__(self, draft_id, expected_version, current_version):
        self.draft_id = draft_id
        self.expected_version = expected_version
        self.current_version = current_version
        super().__init__("The order changed elsewhere. Refresh it before trying again.")


class DraftTakeoverRequired(Exception):
    def __init__(self, draft_id, current_cashier_id):
        self.draft_id = draft_id
        self.current_cashier_id = current_cashier_id
        super().__init__("Resume this order before editing it.")


class BarcodeNowKnown(Exception):
    def __init__(self, product_id, is_active):
        self.product_id = product_id
        self.is_active = bool(is_active)
        super().__init__("This barcode now belongs to an existing product.")


class QuickCreateContextInvalid(Exception):
    """The signed unknown-scan context is unavailable or no longer current."""
