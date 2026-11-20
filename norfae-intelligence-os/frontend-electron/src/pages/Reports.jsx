import { useState } from "react";

import api from "../services/api";

import DatePicker from "react-datepicker";

import { toast } from "sonner";

import "react-datepicker/dist/react-datepicker.css";

import {
  getTodayRange,
  getYesterdayRange,
  getWeekRange,
  getMonthRange,
  getAllTimeRange,
  formatPakistanDate,
} from "../utils/dateFilters";

export default function Reports() {
  // ===================================
  // STATE
  // ===================================

  const [report, setReport] = useState(null);

  const [loading, setLoading] = useState(false);

  const [exporting, setExporting] = useState(false);

  const [showExportMenu, setShowExportMenu] = useState(false);

  const [selectedFilter, setSelectedFilter] = useState("today");

  const [customStartDate, setCustomStartDate] = useState(null);

  const [customEndDate, setCustomEndDate] = useState(null);

  // ===================================
  // GENERATE REPORT
  // ===================================

  const generateReport = async () => {
    try {
      setLoading(true);

      let range;

      switch (selectedFilter) {
        case "today":
          range = getTodayRange();
          break;

        case "yesterday":
          range = getYesterdayRange();
          break;

        case "week":
          range = getWeekRange();
          break;

        case "month":
          range = getMonthRange();
          break;

        case "all":
          range = getAllTimeRange();
          break;

        case "custom":
          range = {
            startDate: formatPakistanDate(customStartDate),

            endDate: formatPakistanDate(customEndDate),
          };

          break;

        default:
          range = getTodayRange();
      }

      const response = await api.get(
        "/reports/generate",

        {
          params: {
            report_type: "business",

            ...(range.startDate && {
              start_date: range.startDate,
            }),

            ...(range.endDate && {
              end_date: range.endDate,
            }),
          },
        },
      );

      console.log("REPORT RESPONSE:", response.data);

      if (response.data.success) {
        setReport(response.data.report);
        toast.success("Report generated successfully");
      } else {
        console.log(response.data.message);
        toast.error(response.data.message || "Failed to generate report");
      }
    } catch (error) {
      console.log("REPORT ERROR:", error);
      toast.error("Failed to generate report");
    } finally {
      setLoading(false);
    }
  };

  // ===================================
  // EXPORT REPORT
  // ===================================

  const exportReport = async (type) => {
    try {
      setExporting(true);
      let startDate = null;

      let endDate = null;

      if (selectedFilter === "today") {
        const range = getTodayRange();

        startDate = range.startDate;

        endDate = range.endDate;
      } else if (selectedFilter === "yesterday") {
        const range = getYesterdayRange();

        startDate = range.startDate;
        endDate = range.endDate;
      } else if (selectedFilter === "week") {
        const range = getWeekRange();

        startDate = range.startDate;

        endDate = range.endDate;
      } else if (selectedFilter === "month") {
        const range = getMonthRange();

        startDate = range.startDate;

        endDate = range.endDate;
      } else if (selectedFilter === "all") {
        const range = getAllTimeRange();

        startDate = range.startDate;

        endDate = range.endDate;
      } else if (
        selectedFilter === "custom" &&
        customStartDate &&
        customEndDate
      ) {
        startDate = customStartDate.toISOString().split("T")[0];

        endDate = customEndDate.toISOString().split("T")[0];
      }

      const response = await api.get(
        `/reports/export/${type}`,

        {
          params: {
            report_type: "business",
            start_date: startDate,
            end_date: endDate,
          },

          responseType: "blob",
        },
      );

      const url = window.URL.createObjectURL(new Blob([response.data]));

      const link = document.createElement("a");

      link.href = url;

      const extension = type === "excel" ? "xlsx" : "pdf";

      link.setAttribute("download", `norfae_report.${extension}`);

      document.body.appendChild(link);

      link.click();

      link.remove();

      toast.success(`${type.toUpperCase()} report exported successfully`);
    } catch (error) {
      console.error("Export failed", error);
      toast.error("Failed to export report");
    } finally {
      setExporting(false);
    }
  };

  // ===================================
  // UI
  // ===================================

  return (
    <div className="max-w-[1800px] p-6">
      {/* =================================== */}
      {/* HEADER */}
      {/* =================================== */}

      <div className="mb-10">
        <div
          className="
            flex
            flex-col
            xl:flex-row
            xl:items-center
            xl:justify-between
            gap-6
          "
        >
          {/* LEFT */}

          <div>
            <h1
              className="
                text-5xl
                font-black
                tracking-tight
                mb-3
                text-white
              "
            >
              Reports
            </h1>

            <p
              className="
                text-slate-400
                text-xl
              "
            >
              Business intelligence and operational reporting
            </p>
          </div>

          {/* RIGHT */}

          <div className="flex gap-4 flex-wrap relative">
            {/* GENERATE */}

            <button
              onClick={generateReport}
              disabled={loading}
              className="
                h-[64px]
                px-8
                rounded-2xl
                bg-gradient-to-r
                from-cyan-500
                to-blue-600
                hover:scale-[1.02]
                active:scale-[0.98]
                transition-all
                text-white
                font-bold
                text-lg
                shadow-2xl
                shadow-cyan-500/20
                disabled:opacity-50
              "
            >
              {loading ? "Generating..." : "Generate Report"}
            </button>

            {/* EXPORT */}

            <div className="relative">
              <button
                onClick={() => setShowExportMenu(!showExportMenu)}
                className="
                  h-[64px]
                  px-8
                  rounded-2xl
                  bg-slate-900
                  border
                  border-slate-700
                  hover:border-cyan-500
                  transition-all
                  text-white
                  font-bold
                  text-lg
                "
              >
                Export ▼
              </button>

              {/* DROPDOWN */}

              {showExportMenu && (
                <div
                  className="
                    absolute
                    top-[74px]
                    right-0
                    w-[220px]
                    bg-slate-950
                    border
                    border-slate-800
                    rounded-2xl
                    overflow-hidden
                    shadow-2xl
                    z-50
                  "
                >
                  <button
                    disabled={exporting}
                    onClick={() => {
                      exportReport("pdf");

                      setShowExportMenu(false);
                    }}
                    className="
                      w-full
                      px-6
                      py-4
                      text-left
                      text-white
                      hover:bg-slate-900
                      transition-all
                      border-b
                      border-slate-800
                    "
                  >
                    {exporting ? "Exporting..." : "Export PDF"}
                  </button>

                  <button
                    disabled={exporting}
                    onClick={() => {
                      exportReport("excel");

                      setShowExportMenu(false);
                    }}
                    className="
                      w-full
                      px-6
                      py-4
                      text-left
                      text-white
                      hover:bg-slate-900
                      transition-all
                    "
                  >
                    {exporting ? "Exporting..." : "Export Excel"}
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* =================================== */}
      {/* FILTERS */}
      {/* =================================== */}

      <div
        className="
          flex
          flex-wrap
          gap-4
          mb-10
        "
      >
        <FilterButton
          label="Today"
          active={selectedFilter === "today"}
          onClick={() => setSelectedFilter("today")}
        />

        <FilterButton
          label="Yesterday"
          active={selectedFilter === "yesterday"}
          onClick={() => setSelectedFilter("yesterday")}
        />

        <FilterButton
          label="This Week"
          active={selectedFilter === "week"}
          onClick={() => setSelectedFilter("week")}
        />

        <FilterButton
          label="This Month"
          active={selectedFilter === "month"}
          onClick={() => setSelectedFilter("month")}
        />

        <FilterButton
          label="All Time"
          active={selectedFilter === "all"}
          onClick={() => setSelectedFilter("all")}
        />

        <FilterButton
          label="Custom Range"
          active={selectedFilter === "custom"}
          onClick={() => setSelectedFilter("custom")}
        />
      </div>

      {selectedFilter === "custom" && (
        <div
          className="
            flex
            flex-wrap
            items-end
            gap-5
            mb-10
            bg-gradient-to-br
            from-slate-900
            to-slate-950
            border
            border-slate-800
            rounded-3xl
            p-6
          "
        >
          <div className="flex flex-col">
            <p className="text-slate-400 text-sm mb-2">Start Date</p>

            <DatePicker
              selected={customStartDate}
              onChange={(date) => setCustomStartDate(date)}
              dateFormat="dd/MM/yyyy"
              placeholderText="Select Start Date"
              className="
                bg-slate-950
                border
                border-slate-700
                rounded-2xl
                px-5
                py-4
                text-white
                outline-none
                min-w-[240px]
              "
            />
          </div>

          <div className="flex flex-col">
            <p className="text-slate-400 text-sm mb-2">End Date</p>

            <DatePicker
              selected={customEndDate}
              onChange={(date) => setCustomEndDate(date)}
              dateFormat="dd/MM/yyyy"
              placeholderText="Select End Date"
              className="
                bg-slate-950
                border
                border-slate-700
                rounded-2xl
                px-5
                py-4
                text-white
                outline-none
                min-w-[240px]
              "
            />
          </div>
        </div>
      )}

      {/* =================================== */}
      {/* EMPTY STATE */}
      {/* =================================== */}

      {!report && (
        <div
          className="
            bg-gradient-to-br
            from-slate-900
            to-slate-950
            border
            border-slate-800
            rounded-3xl
            p-12
            text-center
          "
        >
          <h2
            className="
              text-3xl
              font-bold
              text-white
              mb-4
            "
          >
            No Reports Generated
          </h2>

          <p
            className="
              text-slate-400
              text-lg
              max-w-[900px]
              mx-auto
              leading-relaxed
            "
          >
            Generate a business intelligence report to analyze operational
            performance, profitability, delivery efficiency and financial
            health.
          </p>
        </div>
      )}

      {/* =================================== */}
      {/* REPORT */}
      {/* =================================== */}

      {report && (
        <div className="space-y-12">
          {/* =================================== */}
          {/* REPORT META */}
          {/* =================================== */}

          <div
            className="
              bg-gradient-to-br
              from-slate-900
              to-slate-950
              border
              border-slate-800
              rounded-3xl
              px-8
              py-6
              flex
              flex-col
              xl:flex-row
              xl:items-center
              xl:justify-between
              gap-6
            "
          >
            <div>
              <p
                className="
                  text-slate-400
                  text-sm
                  mb-2
                "
              >
                Generated At
              </p>

              <h3
                className="
                  text-white
                  text-xl
                  font-bold
                "
              >
                {new Date(report.generated_at).toLocaleString()}
              </h3>
            </div>

            <div>
              <p
                className="
                  text-slate-400
                  text-sm
                  mb-2
                "
              >
                Report Type
              </p>

              <h3
                className="
                  text-cyan-400
                  text-xl
                  font-bold
                  capitalize
                "
              >
                {report.report_type}
              </h3>
            </div>
          </div>

          {/* =================================== */}
          {/* OPERATIONS */}
          {/* =================================== */}

          <SectionHeader
            title="Operations Intelligence"
            subtitle="Order lifecycle and fulfillment analytics"
          />

          <div
            className="
              grid
              grid-cols-1
              sm:grid-cols-2
              xl:grid-cols-5
              gap-5
            "
          >
            <ReportCard
              title="Total Orders"
              value={report.summary.total_orders}
            />

            <ReportCard
              title="Delivered"
              value={report.summary.delivered_orders}
              color="text-green-400"
            />

            <ReportCard
              title="Pending"
              value={report.summary.pending_orders}
              color="text-blue-400"
            />

            <ReportCard
              title="Cancelled"
              value={report.summary.cancelled_orders}
              color="text-red-400"
            />

            <ReportCard
              title="Returned"
              value={report.summary.returned_orders}
              color="text-yellow-400"
            />
          </div>

          {/* =================================== */}
          {/* FINANCIAL */}
          {/* =================================== */}

          <SectionHeader
            title="Financial Intelligence"
            subtitle="Revenue, profitability and business health"
          />

          <div
            className="
              grid
              grid-cols-1
              sm:grid-cols-2
              xl:grid-cols-3
              gap-5
            "
          >
            <ReportCard
              title="Revenue"
              value={`Rs. ${report.summary.net_revenue}`}
              color="text-cyan-400"
            />

            <ReportCard
              title="Gross Profit"
              value={`Rs. ${report.summary.gross_profit}`}
              color="text-lime-400"
            />

            <ReportCard
              title="Net Profit"
              value={`Rs. ${report.summary.true_business_profit}`}
              color={
                report.summary.true_business_profit >= 0
                  ? "text-green-400"
                  : "text-red-400"
              }
            />
          </div>

          {/* =================================== */}
          {/* COST BREAKDOWN */}
          {/* =================================== */}

          <SectionHeader
            title="Cost Breakdown"
            subtitle="Operational and financial expense analysis"
          />

          <div
            className="
              grid
              grid-cols-1
              sm:grid-cols-2
              xl:grid-cols-3
              gap-5
            "
          >
            <ReportCard
              title="Delivery Cost"
              value={`Rs. ${report.summary.delivery_cost}`}
            />

            <ReportCard
              title="Product Cost"
              value={`Rs. ${report.summary.product_cost}`}
            />

            <ReportCard
              title="Marketing Cost"
              value={`Rs. ${report.meta_ads.ad_spend}`}
            />

            <ReportCard
              title="Packaging Cost"
              value={`Rs. ${report.summary.packaging_cost}`}
            />

            <ReportCard
              title="External Expenses"
              value={`Rs. ${report.summary.external_expenses}`}
              color="text-orange-400"
            />
          </div>

          {/* =================================== */}
          {/* PERFORMANCE */}
          {/* =================================== */}

          <SectionHeader
            title="Performance Metrics"
            subtitle="Operational efficiency indicators"
          />

          <div
            className="
              grid
              grid-cols-1
              sm:grid-cols-2
              xl:grid-cols-4
              gap-5
            "
          >
            <ReportCard
              title="Avg Order Value"
              value={`Rs. ${report.summary.average_order_value}`}
            />

            <ReportCard
              title="Delivery Success"
              value={`${report.summary.delivery_success_rate}%`}
              color="text-green-400"
            />

            <ReportCard
              title="Cancellation Rate"
              value={`${report.summary.cancellation_rate}%`}
              color="text-red-400"
            />

            <ReportCard
              title="Return Rate"
              value={`${report.summary.return_rate}%`}
              color="text-yellow-400"
            />
          </div>

          {/* =================================== */}
          {/* FORECAST */}
          {/* =================================== */}

          <SectionHeader
            title="Forecasting"
            subtitle="Revenue projection and profitability outlook"
          />

          <div
            className="
              grid
              grid-cols-1
              xl:grid-cols-2
              gap-5
            "
          >
            <ReportCard
              title="Forecast Revenue"
              value={`Rs. ${report.summary.forecasted_revenue}`}
              color="text-cyan-400"
            />

            <ReportCard
              title="True Profit Margin"
              value={`${report.summary.true_profit_margin}%`}
              color="text-lime-400"
            />
          </div>
        </div>
      )}
    </div>
  );
}

// ===================================
// SECTION HEADER
// ===================================

function SectionHeader({ title, subtitle }) {
  return (
    <div>
      <h2
        className="
          text-3xl
          font-black
          text-white
          mb-2
        "
      >
        {title}
      </h2>

      <p
        className="
          text-slate-400
          text-lg
        "
      >
        {subtitle}
      </p>
    </div>
  );
}

// ===================================
// FILTER BUTTON
// ===================================

function FilterButton({ label, active, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`

        px-6
        py-3
        rounded-2xl
        border
        transition-all
        font-semibold
        text-lg

        ${
          active
            ? `
              bg-cyan-500
              text-black
              border-cyan-400
              shadow-lg
              shadow-cyan-500/20
            `
            : `
              bg-slate-900
              text-slate-300
              border-slate-800
              hover:border-slate-600
              hover:bg-slate-800
            `
        }
      `}
    >
      {label}
    </button>
  );
}

// ===================================
// REPORT CARD
// ===================================

function ReportCard({ title, value, color = "text-white" }) {
  return (
    <div
      className="
        bg-gradient-to-br
        from-slate-900
        to-slate-950
        rounded-3xl
        p-7
        border
        border-slate-800
        hover:border-cyan-500/40
        hover:-translate-y-1
        hover:shadow-2xl
        hover:shadow-cyan-500/10
        transition-all
        min-h-[180px]
        flex
        flex-col
        justify-between
      "
    >
      <p
        className="
          text-slate-400
          text-lg
          font-medium
        "
      >
        {title}
      </p>

      <h2
        className={`
          text-4xl
          font-black
          tracking-tight
          leading-none
          ${color}
        `}
      >
        {value}
      </h2>
    </div>
  );
}
