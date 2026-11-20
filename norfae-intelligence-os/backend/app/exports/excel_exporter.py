from io import BytesIO

from openpyxl import Workbook

from openpyxl.styles import (
    Font,
    PatternFill,
    Alignment,
    Border,
    Side,
)

from openpyxl.chart import BarChart

from openpyxl.chart import PieChart

from openpyxl.chart.label import DataLabelList

from openpyxl.utils import get_column_letter

from app.utils.report_formatters import ReportFormatter

from openpyxl.chart import Reference


class ExcelExporter:

    # ===================================
    # EXPORT BUSINESS REPORT
    # ===================================

    @staticmethod
    def generate_business_report(report_data):

        workbook = Workbook()

        sheet = workbook.active

        sheet.title = "Executive Report"

        # ===================================
        # DATA
        # ===================================

        summary = report_data["summary"]

        meta_ads = report_data.get("meta_ads", {})

        top_cities = report_data.get("top_cities", [])

        report_period = report_data.get("report_period", {})

        # ===================================
        # COLORS
        # ===================================

        cyan_fill = PatternFill(
            start_color="06B6D4",
            end_color="06B6D4",
            fill_type="solid",
        )

        green_fill = PatternFill(
            start_color="22C55E",
            end_color="22C55E",
            fill_type="solid",
        )

        blue_fill = PatternFill(
            start_color="3B82F6",
            end_color="3B82F6",
            fill_type="solid",
        )

        orange_fill = PatternFill(
            start_color="F97316",
            end_color="F97316",
            fill_type="solid",
        )

        teal_fill = PatternFill(
            start_color="14B8A6",
            end_color="14B8A6",
            fill_type="solid",
        )

        dark_fill = PatternFill(
            start_color="0F172A",
            end_color="0F172A",
            fill_type="solid",
        )

        gray_fill = PatternFill(
            start_color="F8FAFC",
            end_color="F8FAFC",
            fill_type="solid",
        )

        # ===================================
        # FONTS
        # ===================================

        title_font = Font(
            bold=True,
            size=22,
            color="FFFFFF",
        )

        section_font = Font(
            bold=True,
            size=16,
            color="111827",
        )

        header_font = Font(
            bold=True,
            size=12,
            color="FFFFFF",
        )

        value_font = Font(
            bold=True,
            size=11,
            color="111827",
        )

        small_font = Font(
            size=10,
            color="64748B",
        )

        # ===================================
        # ALIGNMENT
        # ===================================

        center = Alignment(
            horizontal="center",
            vertical="center",
        )

        left = Alignment(
            horizontal="left",
            vertical="center",
        )

        # ===================================
        # BORDER
        # ===================================

        thin = Side(
            style="thin",
            color="CBD5E1",
        )

        border = Border(
            left=thin,
            right=thin,
            top=thin,
            bottom=thin,
        )

        # ===================================
        # COLUMN WIDTHS
        # ===================================

        for col in range(1, 8):

            sheet.column_dimensions[get_column_letter(col)].width = 28

        # ===================================
        # TITLE
        # ===================================

        sheet.merge_cells("A1:G2")

        title_cell = sheet["A1"]

        title_cell.value = (
            "NORFAE INTELLIGENCE OS\n" "Executive Business Intelligence Report"
        )

        title_cell.font = title_font

        title_cell.fill = dark_fill

        title_cell.alignment = center

        # ===================================
        # REPORT META
        # ===================================

        meta_row = 5

        meta_data = [
            (
                "Ad Spend",
                ReportFormatter.currency(meta_ads.get("ad_spend", 0)),
            ),
            (
                "Total Orders",
                summary["total_orders"],
            ),
            (
                "Instagram Messages",
                meta_ads.get("messages", 0),
            ),
        ]

        for title, value in meta_data:

            sheet[f"A{meta_row}"] = title

            sheet[f"B{meta_row}"] = value

            sheet[f"A{meta_row}"].fill = dark_fill

            sheet[f"A{meta_row}"].font = header_font

            sheet[f"A{meta_row}"].alignment = left

            sheet[f"B{meta_row}"].font = value_font

            sheet[f"A{meta_row}"].border = border

            sheet[f"B{meta_row}"].border = border

            meta_row += 1

        # ===================================
        # KPI SECTION
        # ===================================

        sheet.merge_cells("A10:G10")

        sheet["A10"] = "Executive KPIs"

        sheet["A10"].font = section_font

        kpi_data = [
            (
                "Net Revenue",
                ReportFormatter.currency(summary["net_revenue"]),
            ),
            (
                "Net Profit",
                ReportFormatter.currency(summary["net_profit"]),
            ),
            (
                "Profit Margin",
                ReportFormatter.percentage(summary["true_profit_margin"]),
            ),
            (
                "Delivery Success",
                ReportFormatter.percentage(summary["delivery_success_rate"]),
            ),
        ]

        kpi_row = 12

        for index, (title, value) in enumerate(kpi_data):

            col1 = 1 if index % 2 == 0 else 4

            col2 = col1 + 1

            sheet.cell(
                row=kpi_row,
                column=col1,
            ).value = title

            sheet.cell(
                row=kpi_row + 1,
                column=col1,
            ).value = value

            for r in [kpi_row, kpi_row + 1]:

                for c in [col1, col2]:

                    cell = sheet.cell(row=r, column=c)

                    cell.fill = dark_fill

                    cell.border = border

                    cell.alignment = center

                    cell.font = header_font if r == kpi_row else title_font

            if index % 2 == 1:

                kpi_row += 4

        # ===================================
        # REVENUE CHART DATA
        # ===================================

        chart_row = 22

        sheet[f"A{chart_row}"] = "Revenue Analytics"

        sheet[f"A{chart_row}"].font = section_font

        chart_data = [
            ("Revenue", summary["net_revenue"]),
            ("Order Costs", summary["order_costs"]),
            ("Business Profit", summary["true_business_profit"]),
        ]

        data_start = chart_row + 2

        for item in chart_data:

            sheet.append(item)

        # ===================================
        # BAR CHART
        # ===================================

        chart = BarChart()

        chart.title = "Revenue Performance"

        chart.height = 8

        chart.width = 16

        data = Reference(
            sheet,
            min_col=2,
            min_row=data_start,
            max_row=data_start + 2,
        )

        categories = Reference(
            sheet,
            min_col=1,
            min_row=data_start,
            max_row=data_start + 2,
        )

        chart.add_data(data)

        chart.set_categories(categories)

        sheet.add_chart(chart, "D22")

        # ===================================
        # OPERATIONS SECTION
        # ===================================

        section_row = 32

        sheet[f"A{section_row}"] = "Operations Intelligence"

        sheet[f"A{section_row}"].font = section_font

        operations = [
            (
                "Total Orders",
                summary["total_orders"],
            ),
            (
                "Delivered Orders",
                summary["delivered_orders"],
            ),
            (
                "Pending Orders",
                summary["pending_orders"],
            ),
            (
                "Cancelled Orders",
                summary["cancelled_orders"],
            ),
            (
                "Returned Orders",
                summary["returned_orders"],
            ),
        ]

        row = section_row + 2

        for metric, value in operations:

            sheet[f"A{row}"] = metric

            sheet[f"B{row}"] = value

            sheet[f"A{row}"].fill = cyan_fill

            sheet[f"A{row}"].font = header_font

            sheet[f"A{row}"].border = border

            sheet[f"B{row}"].border = border

            row += 1

        # ===================================
        # COST BREAKDOWN
        # ===================================

        row += 3

        sheet[f"A{row}"] = "Cost Breakdown"

        sheet[f"A{row}"].font = section_font

        row += 2

        costs = [
            (
                "Delivery Cost",
                summary["delivery_cost"],
            ),
            (
                "Product Cost",
                summary["product_cost"],
            ),
            (
                "Packaging Cost",
                summary["packaging_cost"],
            ),
            (
                "External Expenses",
                summary["external_expenses"],
            ),
        ]

        for metric, value in costs:

            sheet[f"A{row}"] = metric

            sheet[f"B{row}"] = ReportFormatter.currency(value)

            sheet[f"A{row}"].fill = orange_fill

            sheet[f"A{row}"].font = header_font

            sheet[f"A{row}"].border = border

            sheet[f"B{row}"].border = border

            row += 1

        # ===================================
        # EXPENSE PIE CHART DATA
        # ===================================

        expense_chart_start = row + 2

        expense_data = [
            ("Delivery", summary["delivery_cost"]),
            ("Product", summary["product_cost"]),
            ("Packaging", summary["packaging_cost"]),
            ("External", summary["external_expenses"]),
        ]

        for name, value in expense_data:

            sheet[f"A{expense_chart_start}"] = name
            sheet[f"B{expense_chart_start}"] = value

            expense_chart_start += 1

        expense_pie = PieChart()

        expense_pie.title = "Expense Distribution"

        labels = Reference(
            sheet,
            min_col=1,
            min_row=row + 2,
            max_row=expense_chart_start - 1,
        )

        data = Reference(
            sheet,
            min_col=2,
            min_row=row + 2,
            max_row=expense_chart_start - 1,
        )

        expense_pie.add_data(data)

        expense_pie.set_categories(labels)

        expense_pie.height = 10

        expense_pie.width = 12

        expense_pie.dataLabels = DataLabelList()

        expense_pie.dataLabels.showPercent = True

        expense_chart_row = row + 2

        sheet.add_chart(
            expense_pie,
            f"D{expense_chart_row}",
        )

        row = expense_chart_start + 18

        # ===================================
        # META ADS SECTION
        # ===================================

        row += 3

        sheet[f"A{row}"] = "Meta Ads ROAS Intelligence"

        sheet[f"A{row}"].font = section_font

        row += 2

        meta_data = [
            (
                "Ad Spend",
                ReportFormatter.currency(meta_ads.get("ad_spend", 0)),
            ),
            (
                "Orders",
                meta_ads.get("orders", 0),
            ),
            (
                "Instagram Messages",
                meta_ads.get("messages", 0),
            ),
        ]

        for metric, value in meta_data:

            sheet[f"A{row}"] = metric

            sheet[f"B{row}"] = value

            sheet[f"A{row}"].fill = green_fill

            sheet[f"A{row}"].font = header_font

            sheet[f"A{row}"].border = border

            sheet[f"B{row}"].border = border

            row += 1

        # ===================================
        # CITY HEATMAP
        # ===================================

        row += 3

        sheet[f"A{row}"] = "Delivery City Heatmap"

        sheet[f"A{row}"].font = section_font

        row += 2

        city_chart_start_row = row

        for city, orders in top_cities:

            sheet[f"A{row}"] = city

            # IMPORTANT
            # KEEP NUMERIC VALUE
            sheet[f"B{row}"] = orders

            sheet[f"C{row}"] = f"{orders} Orders"

            sheet[f"A{row}"].fill = teal_fill

            sheet[f"A{row}"].font = header_font

            sheet[f"A{row}"].border = border

            sheet[f"B{row}"].border = border

            sheet[f"C{row}"].border = border

            row += 1

        # ===================================
        # PIE CHART
        # ===================================

        pie = PieChart()

        pie.title = "City Distribution"

        pie_labels = Reference(
            sheet,
            min_col=1,
            min_row=city_chart_start_row,
            max_row=row - 1,
        )

        pie_data = Reference(
            sheet,
            min_col=2,
            min_row=city_chart_start_row,
            max_row=row - 1,
        )

        pie.add_data(pie_data)

        pie.set_categories(pie_labels)

        pie.height = 10

        pie.width = 12

        pie.dataLabels = DataLabelList()

        pie.dataLabels.showPercent = True

        city_chart_position = city_chart_start_row

        sheet.add_chart(
            pie,
            f"D{city_chart_position}",
        )

        # ===================================
        # AI INSIGHTS
        # ===================================

        row += 18

        sheet[f"A{row}"] = "AI Operational Insights"

        sheet[f"A{row}"].font = section_font

        row += 2

        insights = []

        if summary["delivery_success_rate"] < 70:

            insights.append("Delivery success rate below operational threshold.")

        if summary["cancellation_rate"] > 15:

            insights.append("Cancellation rate requires operational review.")

        if summary["true_profit_margin"] > 40:

            insights.append("Profitability operating at healthy levels.")

        if len(insights) == 0:

            insights.append("Business operations stable.")

        for insight in insights:

            sheet.merge_cells(
                start_row=row,
                start_column=1,
                end_row=row,
                end_column=5,
            )

            cell = sheet.cell(
                row=row,
                column=1,
            )

            cell.value = f"• {insight}"

            cell.font = value_font

            cell.fill = gray_fill

            cell.border = border

            row += 2

        # ===================================
        # SIGNATURE SECTION
        # ===================================

        row += 4

        sheet[f"A{row}"] = "Prepared By"

        sheet[f"D{row}"] = "Approved By"

        row += 2

        sheet[f"A{row}"] = "Norfae Intelligence OS"

        sheet[f"D{row}"] = "Management"

        # ===================================
        # VALIDATE MERGED CELLS
        # ===================================

        for sheet_name in workbook.sheetnames:

            ws = workbook[sheet_name]

            for merged_cell in list(ws.merged_cells.ranges):

                try:
                    str(merged_cell)

                except:
                    pass

        # ===================================
        # SAVE FILE
        # ===================================

        excel_file = BytesIO()

        workbook.save(excel_file)

        excel_file.seek(0)

        return excel_file
