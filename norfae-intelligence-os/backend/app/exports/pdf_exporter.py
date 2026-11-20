from io import BytesIO

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)

from reportlab.lib import colors

from reportlab.lib.styles import getSampleStyleSheet

from reportlab.lib.pagesizes import letter

from reportlab.platypus.flowables import HRFlowable

from reportlab.pdfgen import canvas

from reportlab.graphics.shapes import Drawing

from reportlab.graphics.charts.barcharts import VerticalBarChart

from app.utils.report_formatters import ReportFormatter

from reportlab.graphics.charts.piecharts import Pie


class PDFExporter:

    # ===================================
    # PAGE NUMBER
    # ===================================

    @staticmethod
    def add_page_number(canvas, doc):

        page_num = canvas.getPageNumber()

        canvas.setFont("Helvetica", 9)

        canvas.setFillColor(colors.HexColor("#6B7280"))

        canvas.drawRightString(
            570,
            20,
            f"Page {page_num}",
        )

    # ===================================
    # REVENUE CHART
    # ===================================

    @staticmethod
    def build_revenue_chart(summary):

        drawing = Drawing(450, 220)

        chart = VerticalBarChart()

        chart.x = 50

        chart.y = 50

        chart.height = 150

        chart.width = 360

        chart.data = [
            [
                summary["net_revenue"],
                summary["order_costs"],
                summary["true_business_profit"],
            ]
        ]

        chart.categoryAxis.categoryNames = [
            "Revenue",
            "Order Costs",
            "Business Profit",
        ]

        chart.valueAxis.valueMin = 0

        chart.bars[0].fillColor = colors.HexColor("#06B6D4")

        chart.strokeColor = colors.HexColor("#CBD5E1")

        chart.categoryAxis.labels.boxAnchor = "n"

        chart.categoryAxis.labels.angle = 15

        chart.valueAxis.visibleGrid = True

        drawing.add(chart)

        return drawing

    # ===================================
    # EXPENSE PIE CHART
    # ===================================

    @staticmethod
    def build_expense_chart(summary):

        drawing = Drawing(420, 250)

        pie = Pie()

        pie.x = 80
        pie.y = 20

        pie.width = 250
        pie.height = 180

        pie.data = [
            summary["delivery_cost"],
            summary["product_cost"],
            summary["packaging_cost"],
            summary["external_expenses"],
        ]

        pie.labels = [
            "Delivery",
            "Product",
            "Packaging",
            "External",
        ]

        pie.sideLabels = True
        pie.simpleLabels = False

        pie.slices.strokeWidth = 0.5
        pie.slices[0].fillColor = colors.HexColor("#3B82F6")  # Delivery
        pie.slices[1].fillColor = colors.HexColor("#22C55E")  # Product
        pie.slices[2].fillColor = colors.HexColor("#F97316")  # Packaging
        pie.slices[3].fillColor = colors.HexColor("#EF4444")  # External

        drawing.add(pie)

        return drawing

    # ===================================
    # CITY PIE CHART
    # ===================================

    @staticmethod
    def build_city_chart(top_cities):

        drawing = Drawing(420, 250)

        pie = Pie()

        pie.x = 80
        pie.y = 20

        pie.width = 250
        pie.height = 180

        pie.data = []

        pie.labels = []

        for city, orders in top_cities:

            pie.data.append(orders)

            pie.labels.append(city)

        pie.sideLabels = True
        pie.simpleLabels = False

        pie.slices.strokeWidth = 0.5
        city_colors = [
            colors.HexColor("#06B6D4"),
            colors.HexColor("#3B82F6"),
            colors.HexColor("#22C55E"),
            colors.HexColor("#F97316"),
            colors.HexColor("#EF4444"),
            colors.HexColor("#8B5CF6"),
        ]

        for i in range(len(pie.data)):
            pie.slices[i].fillColor = city_colors[i % len(city_colors)]

        drawing.add(pie)

        return drawing

    # ===================================
    # KPI CARD TABLE
    # ===================================

    @staticmethod
    def build_kpi_cards(summary):

        styles = getSampleStyleSheet()

        def build_card(title, value, color):

            return Paragraph(
                f"""
                <font size="11" color="#94A3B8">
                {title}
                </font>

                <br/><br/>

                <font size="18" color="{color}">
                <b>{value}</b>
                </font>
                """,
                styles["BodyText"],
            )

        card_data = [
            [
                build_card(
                    "Revenue",
                    ReportFormatter.currency(summary["net_revenue"]),
                    "#06B6D4",
                ),
                build_card(
                    "Net Profit",
                    ReportFormatter.currency(summary["net_profit"]),
                    "#22C55E",
                ),
            ],
            [
                build_card(
                    "Profit Margin",
                    ReportFormatter.percentage(summary["true_profit_margin"]),
                    "#A3E635",
                ),
                build_card(
                    "Delivery Success",
                    ReportFormatter.percentage(summary["delivery_success_rate"]),
                    "#3B82F6",
                ),
            ],
        ]

        cards = Table(
            card_data,
            colWidths=[250, 250],
            rowHeights=[100, 100],
        )

        cards.setStyle(
            TableStyle(
                [
                    (
                        "BACKGROUND",
                        (0, 0),
                        (-1, -1),
                        colors.HexColor("#0F172A"),
                    ),
                    (
                        "GRID",
                        (0, 0),
                        (-1, -1),
                        10,
                        colors.white,
                    ),
                    (
                        "VALIGN",
                        (0, 0),
                        (-1, -1),
                        "MIDDLE",
                    ),
                    (
                        "LEFTPADDING",
                        (0, 0),
                        (-1, -1),
                        20,
                    ),
                    (
                        "RIGHTPADDING",
                        (0, 0),
                        (-1, -1),
                        20,
                    ),
                    (
                        "TOPPADDING",
                        (0, 0),
                        (-1, -1),
                        20,
                    ),
                    (
                        "BOTTOMPADDING",
                        (0, 0),
                        (-1, -1),
                        20,
                    ),
                ]
            )
        )

        return cards

    # ===================================
    # BUILD METRIC TABLE
    # ===================================

    @staticmethod
    def build_metric_table(title, data, color="#06B6D4"):

        styles = getSampleStyleSheet()

        elements = []

        title_paragraph = Paragraph(
            f"""
            <font size=18 color='{color}'>
            <b>{title}</b>
            </font>
            """,
            styles["Heading2"],
        )

        elements.append(title_paragraph)

        elements.append(Spacer(1, 12))

        table_data = [["Metric", "Value"]]

        for metric_name, value in data:

            table_data.append([metric_name, value])

        table = Table(
            table_data,
            colWidths=[260, 220],
        )

        table.setStyle(
            TableStyle(
                [
                    (
                        "BACKGROUND",
                        (0, 0),
                        (-1, 0),
                        colors.HexColor(color),
                    ),
                    (
                        "TEXTCOLOR",
                        (0, 0),
                        (-1, 0),
                        colors.white,
                    ),
                    (
                        "FONTNAME",
                        (0, 0),
                        (-1, 0),
                        "Helvetica-Bold",
                    ),
                    (
                        "FONTSIZE",
                        (0, 0),
                        (-1, -1),
                        11,
                    ),
                    (
                        "BOTTOMPADDING",
                        (0, 0),
                        (-1, 0),
                        12,
                    ),
                    (
                        "GRID",
                        (0, 0),
                        (-1, -1),
                        1,
                        colors.HexColor("#CBD5E1"),
                    ),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [
                            colors.white,
                            colors.HexColor("#F8FAFC"),
                        ],
                    ),
                    (
                        "TOPPADDING",
                        (0, 1),
                        (-1, -1),
                        8,
                    ),
                    (
                        "BOTTOMPADDING",
                        (0, 1),
                        (-1, -1),
                        8,
                    ),
                ]
            )
        )

        elements.append(table)

        return elements

    # ===================================
    # EXPORT BUSINESS REPORT
    # ===================================

    @staticmethod
    def generate_business_report(report_data):

        pdf_file = BytesIO()

        document = SimpleDocTemplate(
            pdf_file,
            pagesize=letter,
            rightMargin=35,
            leftMargin=35,
            topMargin=35,
            bottomMargin=35,
        )

        styles = getSampleStyleSheet()

        elements = []

        summary = report_data["summary"]

        report_period = report_data.get("report_period", {})

        start_date = report_period.get(
            "start_date",
            "N/A",
        )

        end_date = report_period.get(
            "end_date",
            "N/A",
        )

        # ===================================
        # HEADER
        # ===================================

        title = Paragraph(
            """
            <para align=center>

            <font size=28 color='#06B6D4'>
            <b>NORFAE INTELLIGENCE OS</b>
            </font>

            <br/><br/>

            <font size=20 color='#111827'>
            Executive Business Intelligence Report
            </font>

            </para>
            """,
            styles["Title"],
        )

        elements.append(title)

        elements.append(Spacer(1, 20))

        # ===================================
        # META TABLE
        # ===================================

        meta_table = Table(
            [
                [
                    "Report Type",
                    report_data["report_type"].title(),
                ],
                [
                    "Generated At",
                    ReportFormatter.date(report_data["generated_at"]),
                ],
                [
                    "Report Period",
                    f"{start_date} → {end_date}",
                ],
            ],
            colWidths=[220, 280],
        )

        meta_table.setStyle(
            TableStyle(
                [
                    (
                        "BACKGROUND",
                        (0, 0),
                        (-1, -1),
                        colors.HexColor("#0F172A"),
                    ),
                    (
                        "TEXTCOLOR",
                        (0, 0),
                        (-1, -1),
                        colors.white,
                    ),
                    (
                        "GRID",
                        (0, 0),
                        (-1, -1),
                        1,
                        colors.HexColor("#06B6D4"),
                    ),
                    (
                        "FONTNAME",
                        (0, 0),
                        (-1, -1),
                        "Helvetica-Bold",
                    ),
                    (
                        "FONTSIZE",
                        (0, 0),
                        (-1, -1),
                        13,
                    ),
                    (
                        "TOPPADDING",
                        (0, 0),
                        (-1, -1),
                        12,
                    ),
                    (
                        "BOTTOMPADDING",
                        (0, 0),
                        (-1, -1),
                        12,
                    ),
                ]
            )
        )

        elements.append(meta_table)

        elements.append(Spacer(1, 25))

        # ===================================
        # KPI SECTION
        # ===================================

        kpi_title = Paragraph(
            """
            <font size=20 color='#111827'>
            <b>Executive KPIs</b>
            </font>
            """,
            styles["Heading1"],
        )

        elements.append(kpi_title)

        elements.append(Spacer(1, 15))

        elements.append(PDFExporter.build_kpi_cards(summary))

        elements.append(Spacer(1, 30))

        chart_title = Paragraph(
            """
            <font size=18 color='#111827'>
            <b>Revenue & Profitability Chart</b>
            </font>
            """,
            styles["Heading2"],
        )

        elements.append(chart_title)

        elements.append(Spacer(1, 15))

        elements.append(PDFExporter.build_revenue_chart(summary))

        elements.append(Spacer(1, 35))

        elements.append(Spacer(1, 30))

        # ===================================
        # OPERATIONS
        # ===================================

        operations_data = [
            ("Total Orders", str(summary["total_orders"])),
            ("Delivered Orders", str(summary["delivered_orders"])),
            ("Pending Orders", str(summary["pending_orders"])),
            ("Cancelled Orders", str(summary["cancelled_orders"])),
            ("Returned Orders", str(summary["returned_orders"])),
        ]

        elements.extend(
            PDFExporter.build_metric_table(
                "Operations Intelligence",
                operations_data,
                "#06B6D4",
            )
        )

        elements.append(Spacer(1, 25))

        # ===================================
        # FINANCIAL
        # ===================================

        financial_data = [
            (
                "Revenue",
                ReportFormatter.currency(summary["net_revenue"]),
            ),
            (
                "Net Profit",
                ReportFormatter.currency(summary["net_profit"]),
            ),
            (
                "True Business Profit",
                ReportFormatter.currency(summary["true_business_profit"]),
            ),
        ]

        elements.extend(
            PDFExporter.build_metric_table(
                "Financial Intelligence",
                financial_data,
                "#22C55E",
            )
        )

        elements.append(Spacer(1, 25))

        expense_chart_title = Paragraph(
            """
        <font size=18 color='#111827'>
        <b>Expense Distribution</b>
        </font>
        """,
            styles["Heading2"],
        )

        elements.append(expense_chart_title)

        elements.append(Spacer(1, 12))

        elements.append(PDFExporter.build_expense_chart(summary))

        elements.append(Spacer(1, 20))

        # ===================================
        # COST BREAKDOWN
        # ===================================

        cost_data = [
            (
                "Delivery Cost",
                ReportFormatter.currency(summary["delivery_cost"]),
            ),
            (
                "Product Cost",
                ReportFormatter.currency(summary["product_cost"]),
            ),
            (
                "Packaging Cost",
                ReportFormatter.currency(summary["packaging_cost"]),
            ),
            (
                "External Expenses",
                ReportFormatter.currency(summary["external_expenses"]),
            ),
        ]

        elements.extend(
            PDFExporter.build_metric_table(
                "Cost Breakdown",
                cost_data,
                "#F97316",
            )
        )

        elements.append(Spacer(1, 25))

        # ===================================
        # PERFORMANCE
        # ===================================

        performance_data = [
            (
                "Average Order Value",
                ReportFormatter.currency(summary["average_order_value"]),
            ),
            (
                "Delivery Success Rate",
                ReportFormatter.percentage(summary["delivery_success_rate"]),
            ),
            (
                "Cancellation Rate",
                ReportFormatter.percentage(summary["cancellation_rate"]),
            ),
            (
                "Return Rate",
                ReportFormatter.percentage(summary["return_rate"]),
            ),
        ]

        elements.extend(
            PDFExporter.build_metric_table(
                "Performance Metrics",
                performance_data,
                "#3B82F6",
            )
        )

        elements.append(Spacer(1, 25))

        # ===================================
        # META ADS
        # ===================================

        meta_ads = report_data.get("meta_ads", {})

        meta_ads_data = [
            (
                "Meta Ads Spend",
                ReportFormatter.currency(meta_ads.get("ad_spend", 0)),
            ),
            (
                "Orders",
                str(meta_ads.get("orders", 0)),
            ),
            (
                "Instagram Messages",
                str(meta_ads.get("messages", 0)),
            ),
        ]

        elements.extend(
            PDFExporter.build_metric_table(
                "Meta Ads Performance",
                meta_ads_data,
                "#F97316",
            )
        )

        elements.append(Spacer(1, 25))

        # ===================================
        # CITY DISTRIBUTION
        # ===================================

        city_chart_title = Paragraph(
            """
        <font size=18 color='#111827'>
        <b>City Distribution</b>
        </font>
        """,
            styles["Heading2"],
        )

        elements.append(city_chart_title)

        elements.append(Spacer(1, 12))

        elements.append(PDFExporter.build_city_chart(report_data.get("top_cities", [])))

        elements.append(Spacer(1, 20))

        # ===================================
        # DELIVERY HEATMAP
        # ===================================

        heatmap_data = []

        for city, total_orders in report_data.get("top_cities", []):

            heatmap_data.append(
                (
                    city,
                    f"{total_orders} Orders",
                )
            )

        elements.extend(
            PDFExporter.build_metric_table(
                "Delivery City Heatmap",
                heatmap_data,
                "#14B8A6",
            )
        )

        elements.append(Spacer(1, 30))

        # ===================================
        # AI INSIGHTS
        # ===================================

        insights_title = Paragraph(
            """
            <font size=18 color='#111827'>
            <b>AI Operational Insights</b>
            </font>
            """,
            styles["Heading2"],
        )

        elements.append(insights_title)

        elements.append(Spacer(1, 15))

        insights = []

        if summary["delivery_success_rate"] < 70:

            insights.append("Delivery success rate is below operational threshold.")

        if summary["cancellation_rate"] > 15:

            insights.append("Cancellation rate requires operational investigation.")

        if summary["true_profit_margin"] > 40:

            insights.append("Business profitability is operating at a healthy level.")

        if len(insights) == 0:

            insights.append("Business operations are stable.")

        for insight in insights:

            paragraph = Paragraph(
                f"""
                <font size=11 color='#111827'>
                • {insight}
                </font>
                """,
                styles["BodyText"],
            )

            elements.append(paragraph)

            elements.append(Spacer(1, 8))

        # ===================================
        # SIGNATURE SECTION
        # ===================================

        elements.append(Spacer(1, 40))

        signature_table = Table(
            [
                [
                    "Prepared By",
                    "Approved By",
                ],
                [
                    "Norfae Intelligence OS",
                    "Management",
                ],
            ],
            colWidths=[250, 250],
        )

        signature_table.setStyle(
            TableStyle(
                [
                    (
                        "LINEABOVE",
                        (0, 1),
                        (-1, 1),
                        1,
                        colors.black,
                    ),
                    (
                        "TOPPADDING",
                        (0, 1),
                        (-1, 1),
                        20,
                    ),
                    (
                        "FONTNAME",
                        (0, 0),
                        (-1, -1),
                        "Helvetica-Bold",
                    ),
                    (
                        "ALIGN",
                        (0, 0),
                        (-1, -1),
                        "CENTER",
                    ),
                ]
            )
        )

        elements.append(signature_table)

        elements.append(Spacer(1, 30))

        # ===================================
        # FOOTER
        # ===================================

        divider = HRFlowable(
            width="100%",
            color=colors.HexColor("#CBD5E1"),
        )

        elements.append(divider)

        elements.append(Spacer(1, 10))

        footer = Paragraph(
            """
            <para align=center>

            <font size=10 color='#6B7280'>
            Norfae Intelligence OS • Confidential Executive Report
            </font>

            </para>
            """,
            styles["BodyText"],
        )

        elements.append(footer)

        # ===================================
        # BUILD PDF
        # ===================================

        document.build(
            elements,
            onFirstPage=PDFExporter.add_page_number,
            onLaterPages=PDFExporter.add_page_number,
        )

        pdf_file.seek(0)

        return pdf_file
