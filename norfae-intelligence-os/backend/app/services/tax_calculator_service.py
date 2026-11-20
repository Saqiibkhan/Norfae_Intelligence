class TaxCalculatorService:

    GST_PERCENTAGE = 16
    INCOME_TAX_PERCENTAGE = 4

    @staticmethod
    def calculate_gst(amount: float):

        gst = (
            amount *
            TaxCalculatorService.GST_PERCENTAGE
        ) / 100

        return round(gst, 2)

    @staticmethod
    def calculate_income_tax(profit: float):

        income_tax = (
            profit *
            TaxCalculatorService.INCOME_TAX_PERCENTAGE
        ) / 100

        return round(income_tax, 2)