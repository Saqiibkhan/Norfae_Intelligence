import DatePicker from "react-datepicker";

import "react-datepicker/dist/react-datepicker.css";

import React, { useEffect, useState, useCallback } from "react";

import { toast } from "sonner";

import api from "../lib/api";

import RevenueChart from "../components/dashboard/RevenueChart";

import ProfitChart from "../components/dashboard/ProfitChart";

import OrdersChart from "../components/dashboard/OrdersChart";

import DeliveryChart from "../components/dashboard/DeliveryChart";

import {
  getTodayRange,
  getYesterdayRange,
  getWeekRange,
  getMonthRange,
  getAllTimeRange,
  formatPakistanDate,
} from "../utils/dateFilters";

import {
  ShoppingCart,
  Clock3,
  Truck,
  CheckCircle2,
  XCircle,
  RotateCcw,
  Wallet,
  TruckIcon,
  Receipt,
  CircleDollarSign,
  BadgeDollarSign,
  BarChart3,
  ShieldCheck,
  Percent,
  Undo2,
  Activity,
} from "lucide-react";

function Dashboard() {
  const [stats, setStats] = useState({
    gross_profit: 0,

    return_loss: 0,

    marketing_cost: 0,

    operating_expenses: 0,

    product_cost: 0,

    packaging_cost: 0,
    total_orders: 0,

    delivered_orders: 0,

    cancelled_orders: 0,

    returned_orders: 0,

    pending_orders: 0,

    revenue: 0,

    delivery_costs: 0,

    expenses: 0,

    profit: 0,

    true_business_profit: 0,

    total_products: 0,

    health_score: 0,

    average_order_value: 0,

    delivery_success_rate: 0,

    cancellation_rate: 0,

    return_rate: 0,
  });

  const [selectedFilter, setSelectedFilter] = useState("today");

  const [loading, setLoading] = useState(false);

  const [customStartDate, setCustomStartDate] = useState(null);

  const [customEndDate, setCustomEndDate] = useState(null);

  const [trendData, setTrendData] = useState([]);

  const [comparisonData, setComparisonData] = useState({});

  const fetchDashboard = useCallback(async () => {
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

      const analyticsResponse = await api.get("/orders/analytics", {
        params: {
          ...(range.startDate && {
            start_date: range.startDate,
          }),

          ...(range.endDate && {
            end_date: range.endDate,
          }),
        },
      });

      const trendsResponse = await api.get("/orders/analytics/trends", {
        params: {
          ...(range.startDate && {
            start_date: range.startDate,
          }),

          ...(range.endDate && {
            end_date: range.endDate,
          }),
        },
      });
      console.log("TRENDS:", trendsResponse.data);

      console.log(trendsResponse.data);

      setTrendData(trendsResponse.data.trends);

      const dashboardResponse = await api.get("/dashboard/overview", {
        params: {
          ...(range.startDate && {
            start_date: range.startDate,
          }),

          ...(range.endDate && {
            end_date: range.endDate,
          }),
        },
      });

      const analytics = analyticsResponse.data?.summary || {};
      console.log("ANALYTICS:", analytics);
      const dashboard = dashboardResponse.data || {};
      console.log("DASHBOARD:", dashboard);

      let comparison = {};

      try {
        const comparisonResponse = await api.get(
          "/orders/analytics/comparison",
          {
            params: {
              ...(range.startDate && {
                start_date: range.startDate,
              }),

              ...(range.endDate && {
                end_date: range.endDate,
              }),
            },
          },
        );

        comparison = comparisonResponse.data?.comparison || {};
      } catch (error) {
        console.log("Comparison API failed", error);
      }

      setComparisonData(comparison);

      setStats({
        total_orders: analytics?.total_orders || 0,

        delivered_orders: analytics?.delivered_orders || 0,

        cancelled_orders: analytics?.cancelled_orders || 0,

        returned_orders: analytics?.returned_orders || 0,

        pending_orders: dashboard?.pending_orders || 0,

        active_orders: dashboard?.active_orders || 0,

        revenue: dashboard?.revenue || 0,

        gross_profit: dashboard?.gross_profit || 0,

        return_loss: dashboard?.return_loss || 0,

        profit: dashboard?.profit || 0,

        expenses: dashboard?.expenses || 0,

        marketing_cost: dashboard?.marketing_cost || 0,

        operating_expenses: dashboard?.operating_expenses || 0,

        true_business_profit: dashboard?.true_business_profit || 0,

        delivery_costs: dashboard?.delivery_costs || 0,

        product_cost: dashboard?.product_cost || 0,

        packaging_cost: dashboard?.packaging_cost || 0,

        total_products: dashboard?.total_products || 0,

        health_score: dashboard?.health_score || 0,

        average_order_value: analytics?.average_order_value || 0,

        delivery_success_rate: analytics?.delivery_success_rate || 0,

        cancellation_rate: analytics?.cancellation_rate || 0,

        return_rate: analytics?.return_rate || 0,
      });
    } catch (error) {
      console.log(error);
      toast.error("Failed to load dashboard");
    } finally {
      setLoading(false);
    }
  }, [selectedFilter, customStartDate, customEndDate]);

  useEffect(() => {
    const loadDashboard = async () => {
      if (selectedFilter !== "custom") {
        await fetchDashboard();
      }
    };

    loadDashboard();
  }, [fetchDashboard, selectedFilter]);

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
              Dashboard
            </h1>

            <p
              className="
              text-slate-400
              text-xl
            "
            >
              Operational intelligence and commerce analytics
            </p>
          </div>

          <div
            className="
            bg-gradient-to-br
            from-slate-900
            to-slate-950
            border
            border-slate-800
            rounded-3xl
            px-8
            py-8
            min-w-[220px]
          "
          >
            <p
              className="
              text-slate-400
              text-sm
              mb-2
            "
            >
              Active Filter
            </p>

            <h3
              className="
              text-cyan-400
              font-black
              text-3xl
              capitalize
            "
            >
              {selectedFilter}
            </h3>
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
        mb-8
      "
      >
        <FilterButton
          label="Today"
          active={selectedFilter === "today"}
          onClick={() => {
            setSelectedFilter("today");
          }}
        />

        <FilterButton
          label="Yesterday"
          active={selectedFilter === "yesterday"}
          onClick={() => {
            setSelectedFilter("yesterday");
          }}
        />

        <FilterButton
          label="This Week"
          active={selectedFilter === "week"}
          onClick={() => {
            setSelectedFilter("week");
          }}
        />

        <FilterButton
          label="This Month"
          active={selectedFilter === "month"}
          onClick={() => {
            setSelectedFilter("month");
          }}
        />

        <FilterButton
          label="All Time"
          active={selectedFilter === "all"}
          onClick={() => {
            setSelectedFilter("all");
          }}
        />

        <FilterButton
          label="Custom Range"
          active={selectedFilter === "custom"}
          onClick={() => {
            setSelectedFilter("custom");
          }}
        />
      </div>

      {/* =================================== */}
      {/* CUSTOM RANGE */}
      {/* =================================== */}

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
          {/* START DATE */}

          <div className="flex flex-col">
            <p
              className="
                text-slate-400
                text-sm
                mb-2
                font-medium
              "
            >
              Start Date
            </p>

            <DatePicker
              selected={customStartDate}
              onChange={(date) => {
                setCustomStartDate(date);
              }}
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
                  min-w-[260px]
                  focus:border-cyan-400
                  transition-all
                "
            />
          </div>

          {/* END DATE */}

          <div className="flex flex-col">
            <p
              className="
                text-slate-400
                text-sm
                mb-2
                font-medium
              "
            >
              End Date
            </p>

            <DatePicker
              selected={customEndDate}
              onChange={(date) => {
                setCustomEndDate(date);
              }}
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
                  min-w-[260px]
                  focus:border-cyan-400
                  transition-all
                "
            />
          </div>

          {/* APPLY BUTTON */}

          <button
            onClick={() => {
              if (!customStartDate || !customEndDate) {
                toast.error("Please select both dates");
                return;
              }

              fetchDashboard();
            }}
            className="
                bg-cyan-500
                hover:bg-cyan-400
                text-black
                font-bold
                px-8
                py-4
                rounded-2xl
                transition-all
                shadow-lg
                shadow-cyan-500/20
              "
          >
            Apply Filter
          </button>
        </div>
      )}

      {/* =================================== */}
      {/* LOADING */}
      {/* =================================== */}

      {loading && (
        <div
          className="
            mb-8
            text-cyan-400
            font-semibold
            text-lg
          "
        >
          Loading analytics...
        </div>
      )}

      {/* =================================== */}
      {/* OPERATIONS */}
      {/* =================================== */}

      <div className="mb-12">
        <div className="mb-5">
          <h2
            className="
      text-2xl
      font-bold
      text-white
    "
          >
            Operations
          </h2>

          <p
            className="
      text-slate-400
      mt-1
    "
          >
            Order lifecycle analytics
          </p>
        </div>

        <div
          className="
    grid
    grid-cols-1
    sm:grid-cols-2
    lg:grid-cols-3
    2xl:grid-cols-5
    gap-5
  "
        >
          <DashboardCard
            title="Pending Confirmation"
            value={stats.pending_orders}
            color="text-blue-400"
            icon={<Clock3 />}
            iconColor="text-blue-400"
          />

          <DashboardCard
            title="Active Orders"
            value={stats.active_orders}
            color="text-cyan-400"
            icon={<Truck />}
            iconColor="text-cyan-400"
          />
          <DashboardCard
            title="Total Orders"
            value={
              <>
                <style>{`
        @keyframes totalOrdersGlow {
          0%, 100% { 
            opacity: 1;
            filter: drop-shadow(0 0 2px rgba(34,211,238,0.2)); 
          }
          50% { 
            opacity: 0.85;
            filter: drop-shadow(0 0 12px rgba(34,211,238,0.6)); 
          }
        }
        .total-orders-pulse {
          animation: totalOrdersGlow 800ms ease-in-out infinite !important;
        }
      `}</style>
                <span className="bg-gradient-to-r from-emerald-400 via-green-400 to-lime-400 bg-clip-text text-transparent total-orders-pulse">
                  {stats.total_orders}
                </span>
              </>
            }
            icon={<ShoppingCart />}
            iconColor="text-lime-400"
            comparison={comparisonData?.total_orders?.change_percentage}
          />

          <DashboardCard
            title="Delivered"
            value={stats.delivered_orders}
            color="text-green-400"
            icon={<CheckCircle2 />}
            iconColor="text-green-400"
            comparison={comparisonData?.delivered_orders?.change_percentage}
          />

          <DashboardCard
            title="Cancelled"
            value={stats.cancelled_orders}
            color="text-yellow-400"
            icon={<XCircle />}
            iconColor="text-yellow-400"
          />

          <DashboardCard
            title="Returned"
            value={stats.returned_orders}
            color="text-red-400"
            icon={<RotateCcw />}
            iconColor="text-red-400"
          />
        </div>
      </div>

      {/* =================================== */}
      {/* FINANCIAL */}
      {/* =================================== */}

      <div className="mb-12">
        <div className="mb-5">
          <h2
            className="
      text-2xl
      font-bold
      text-white
    "
          >
            Financial Intelligence
          </h2>

          <p
            className="
      text-slate-400
      mt-1
    "
          >
            Realized revenue and profitability
          </p>
        </div>

        <div
          className="
    grid
    grid-cols-1
    sm:grid-cols-2
    lg:grid-cols-3
    2xl:grid-cols-5
    gap-5
  "
        >
          <DashboardCard
            title="Revenue"
            value={`Rs. ${stats.revenue}`}
            icon={<Wallet />}
            iconColor="text-cyan-400"
            comparison={comparisonData?.net_revenue?.change_percentage}
          />

          <DashboardCard
            title="Delivery Costs"
            value={`Rs. ${stats.delivery_costs}`}
            icon={<TruckIcon />}
            iconColor="text-orange-400"
          />

          <DashboardCard
            title="Expenses"
            value={`Rs. ${stats.expenses}`}
            icon={<Receipt />}
            iconColor="text-rose-400"
          />

          <DashboardCard
            title="Gross Profit"
            value={`Rs. ${stats.profit}`}
            color={
              stats.profit >= 0
                ? "text-lime-300 drop-shadow-[0_0_16px_rgba(190,242,100,0.45)]"
                : "text-red-400 drop-shadow-[0_0_14px_rgba(248,113,113,0.35)]"
            }
            icon={<CircleDollarSign />}
            iconColor="text-lime-400"
            comparison={comparisonData?.net_profit?.change_percentage}
          />

          <DashboardCard
            title="Net Profit"
            value={`Rs. ${stats.true_business_profit}`}
            color={
              stats.true_business_profit >= 0
                ? "text-green-400 drop-shadow-[0_0_20px_rgba(52,211,153,0.55)]"
                : "text-red-500 drop-shadow-[0_0_16px_rgba(239,68,68,0.45)]"
            }
            icon={<BadgeDollarSign />}
            iconColor="text-green-400"
          />

          <DashboardCard
            title="Avg Order Value"
            value={`Rs. ${stats.average_order_value}`}
            color="text-violet-400"
            icon={<BarChart3 />}
            iconColor="text-violet-400"
            comparison={comparisonData?.average_order_value?.change_percentage}
          />
        </div>
      </div>

      {/* =================================== */}
      {/* PERFORMANCE */}
      {/* =================================== */}

      <div className="mb-12">
        <div className="mb-5">
          <h2
            className="
      text-2xl
      font-bold
      text-white
    "
          >
            Performance Metrics
          </h2>

          <p
            className="
      text-slate-400
      mt-1
    "
          >
            Operational efficiency indicators
          </p>
        </div>

        <div
          className="
    grid
    grid-cols-1
    sm:grid-cols-2
    lg:grid-cols-2
    2xl:grid-cols-4
    gap-5
  "
        >
          <DashboardCard
            title="Delivery Success"
            value={`${stats.delivery_success_rate}%`}
            color="text-green-400"
            comparison={
              comparisonData?.delivery_success_rate?.change_percentage
            }
            icon={<ShieldCheck />}
            iconColor="text-green-400"
          />

          <DashboardCard
            title="Cancellation Rate"
            value={`${stats.cancellation_rate}%`}
            color="text-yellow-400"
            icon={<Percent />}
            iconColor="text-yellow-400"
          />

          <DashboardCard
            title="Return Rate"
            value={`${stats.return_rate}%`}
            color="text-red-400"
            icon={<Undo2 />}
            iconColor="text-red-400"
          />

          <DashboardCard
            title="Health Score"
            value={stats.health_score}
            color="text-cyan-400"
            icon={<Activity />}
            iconColor="text-cyan-400"
          />
        </div>
      </div>
      {/* =================================== */}
      {/* CHARTS */}
      {/* =================================== */}

      <div
        className="
        grid
        grid-cols-1
        2xl:grid-cols-2
        gap-6
        mt-10
      "
      >
        <RevenueChart data={trendData} />

        <ProfitChart data={trendData} />

        <OrdersChart data={trendData} />

        <DeliveryChart data={trendData} />
      </div>
    </div>
  );
}

function FilterButton({
  label,

  active,

  onClick,
}) {
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

function DashboardCard({
  title,
  value,
  color = "",
  comparison,
  icon,
  iconColor = "text-cyan-400",
}) {
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
        min-h-[220px]
        flex
        flex-col
        justify-between
      "
    >
      <div className="flex items-center gap-5">
        <div
          className={`
    w-12
    h-12
    rounded-2xl
    bg-slate-800
    border
    border-slate-700
    flex
    items-center
    justify-center
    shrink-0
    ${iconColor}
  `}
        >
          {icon && React.cloneElement(icon, { size: 25 })}
        </div>

        <p
          className="
      text-white
      text-xl
      font-medium
    "
        >
          {title}
        </p>
      </div>

      <div>
        <h2
          className={`
          text-3xl lg:text-4xl
          font-black
          tracking-tight
          mt-3
          leading-none
          ${color}
        `}
        >
          {value}
        </h2>

        {comparison !== undefined && (
          <div
            className="
      mt-4
      flex
      items-center
      gap-2
    "
          >
            <span
              className={`
        text-sm
        font-bold

        ${comparison >= 0 ? "text-green-400" : "text-red-400"}
      `}
            >
              {comparison >= 0 ? "↑" : "↓"}
              {Math.abs(comparison)}%
            </span>

            <span
              className="
        text-slate-500
        text-sm
      "
            >
              vs previous period
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

export default Dashboard;
