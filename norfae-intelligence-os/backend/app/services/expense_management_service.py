class ExpenseManagementService:

    # ===================================
    # EXPENSE CATEGORY ANALYSIS
    # ===================================

    @staticmethod
    def categorize_expense(
        category: str
    ):

        category = category.lower()

        if category in [
            "ads",
            "marketing"
        ]:

            return "marketing"

        if category in [
            "delivery",
            "shipping"
        ]:

            return "logistics"

        return "operations"