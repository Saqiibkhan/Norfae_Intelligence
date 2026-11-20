import { useEffect, useState, useRef, useCallback } from "react";

import api from "../services/api";

import EditMatchModal from "../components/EditMatchModal";
import EditCityModal from "../components/EditCityModal";
import DatePicker from "react-datepicker";
import { toast } from "sonner";
import "react-datepicker/dist/react-datepicker.css";

import {
  ShoppingCart,
  Clock3,
  Truck,
  CheckCircle2,
  XCircle,
  RotateCcw,
  Wallet,
  BadgeDollarSign,
} from "lucide-react";

export default function Orders() {
  const [selectedItem, setSelectedItem] = useState(null);

  const [showEditModal, setShowEditModal] = useState(false);

  const [showEditCityModal, setShowEditCityModal] = useState(false);

  const [selectedOrderForCity, setSelectedOrderForCity] = useState(null);

  const [orders, setOrders] = useState([]);

  const [dashboardStats, setDashboardStats] = useState({
    pending_orders: 0,
    active_orders: 0,
  });

  const [expandedOrders, setExpandedOrders] = useState({});

  const [loading, setLoading] = useState(true);

  const [filterType, setFilterType] = useState("today");

  const websocketRef = useRef(null);

  const [startDate, setStartDate] = useState("");

  const [endDate, setEndDate] = useState("");

  // ===================================
  // FETCH ORDERS
  // ===================================

  const fetchOrders = useCallback(async () => {
    try {
      const response = await api.get("/orders/", {
        params: {
          filter_type: filterType,
          start_date: startDate,
          end_date: endDate,
        },
      });

      const data = Array.isArray(response.data) ? response.data : [];

      setOrders(data);
    } catch (error) {
      console.error(error);
      toast.error("Failed to load orders");
    } finally {
      setLoading(false);
    }
  }, [filterType, startDate, endDate]);

  const fetchDashboardStats = useCallback(async () => {
    try {
      const response = await api.get("/dashboard/overview");

      setDashboardStats({
        pending_orders: response.data.pending_orders || 0,
        active_orders: response.data.active_orders || 0,
      });
    } catch (error) {
      console.error(error);
    }
  }, []);

  useEffect(() => {
    const loadData = async () => {
      await fetchOrders();
      await fetchDashboardStats();
    };

    loadData();
  }, [fetchOrders, fetchDashboardStats]);

  useEffect(() => {
    const interval = setInterval(() => {
      fetchOrders();
      fetchDashboardStats();
    }, 15000);

    return () => clearInterval(interval);
  }, [fetchOrders, fetchDashboardStats]);

  useEffect(() => {
    const ws = new WebSocket("ws://localhost:8000/ws/orders");

    ws.onopen = () => {
      console.log("Orders websocket connected");
    };

    websocketRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);

        if (payload.event === "order_update") {
          console.log("Realtime order update received:", payload.data);
          setOrders((prevOrders) => {
            const updatedOrder = payload.data;

            const existingIndex = prevOrders.findIndex(
              (o) => o.id === updatedOrder.id,
            );

            // ===============================
            // UPDATE EXISTING
            // ===============================

            if (existingIndex !== -1) {
              const updatedOrders = [...prevOrders];

              updatedOrders[existingIndex] = {
                ...updatedOrders[existingIndex],
                ...updatedOrder,
              };

              updatedOrders.sort((a, b) => {
                const dateA =
                  a.confirmed_order_date ||
                  a.discord_created_at ||
                  a.created_at;

                const dateB =
                  b.confirmed_order_date ||
                  b.discord_created_at ||
                  b.created_at;

                return new Date(dateB) - new Date(dateA);
              });

              return updatedOrders;
            }

            // ===============================
            // NEW ORDER
            // ===============================

            return [updatedOrder, ...prevOrders];
          });
        }
      } catch (error) {
        console.error("WebSocket parse error:", error);
      }
    };

    ws.onerror = (error) => {
      console.error("Orders websocket error:", error);
    };

    ws.onclose = () => {
      console.log("Orders websocket disconnected");
    };

    return () => {
      ws.close();
    };
  }, []);

  // ===================================
  // LOADING
  // ===================================

  if (loading) {
    return (
      <div className="p-10 text-white">Loading Orders Intelligence...</div>
    );
  }

  // ===================================
  // METRICS
  // ===================================

  const totalOrders = orders.length;

  const completedOrders = orders.filter(
    (order) => order.status === "DELIVERED",
  ).length;

  const cancelledOrders = orders.filter(
    (order) => order.status === "CANCELLED",
  ).length;

  const returnedOrders = orders.filter(
    (order) => order.status === "RETURNED",
  ).length;

  const pendingOrders = dashboardStats.pending_orders;

  const activeOrders = dashboardStats.active_orders;

  const deliveredOrders = orders.filter(
    (order) => order.status === "DELIVERED",
  );

  const cancelledOrderList = orders.filter(
    (order) => order.status === "CANCELLED",
  );

  const deliveredRevenue = deliveredOrders.reduce(
    (sum, order) => sum + Number(order.selling_price || 0),
    0,
  );

  const deliveredProfit = deliveredOrders.reduce(
    (sum, order) => sum + Number(order.net_profit || 0),
    0,
  );

  const cancelledRevenue = cancelledOrderList.reduce(
    (sum, order) => sum + Number(order.selling_price || 0),
    0,
  );

  const returnedRevenue = orders
    .filter((order) => order.status === "RETURNED")
    .reduce((sum, order) => sum + Number(order.selling_price || 0), 0);

  const totalRevenue = orders.reduce(
    (sum, order) => sum + Number(order.selling_price || 0),
    0,
  );

  const avgProductCost =
    orders.length > 0
      ? orders.reduce(
          (sum, order) => sum + Number(order.product_cost || 0),
          0,
        ) / orders.length
      : 0;

  // ===================================
  // PRODUCT DISPLAY
  // ===================================
  const renderProducts = (order) => {
    const toggleOrderProducts = (orderId) => {
      setExpandedOrders((prev) => ({
        ...prev,

        [orderId]: !prev[orderId],
      }));
    };

    // ===================================
    // MULTI PRODUCTS
    // ===================================

    if (
      order.products &&
      Array.isArray(order.products) &&
      order.products.length > 1
    ) {
      return (
        <div>
          <button
            onClick={() => toggleOrderProducts(order.id)}
            className="
            flex
            items-center
            gap-2
            bg-[#132347]
            hover:bg-[#1A2F5C]
            border
            border-white/10
            px-3
            py-2
            rounded-xl
            text-white
            text-xs
            font-medium
            transition-all
            duration-200
            w-[110px]
            justify-center
          "
          >
            <span className="text-xs">
              {expandedOrders[order.id] ? "▼" : "▶"}
            </span>{" "}
            {order.products.length} Products
          </button>

          {expandedOrders[order.id] && (
            <div
              className="
                mt-3
                grid
                gap-3
              "
            >
              {order.products.map((product, index) => (
                <div
                  key={index}
                  className="
                      bg-[#101C3D]
                      border
                      border-white/5
                      rounded-xl
                      p-3
                      w-full
                    "
                >
                  <p className="font-semibold text-sm text-white leading-5">
                    {product.name}
                  </p>

                  {product.size && (
                    <p className="text-xs text-slate-400 mt-1">
                      {product.size}
                    </p>
                  )}

                  <p className="text-xs text-gray-400 mt-1">
                    SKU:
                    {product.sku || "UNKNOWN"}
                  </p>

                  <p className="text-xs text-gray-400">
                    Qty:
                    {product.quantity}
                  </p>

                  <button
                    onClick={() => {
                      if (!product.id) {
                        toast.error("This product has no order item.");

                        return;
                      }

                      setSelectedItem({
                        id: product.id,

                        sku: product.sku,

                        quantity: product.quantity,

                        size: product.size,
                      });

                      setShowEditModal(true);
                    }}
                    className="
                        flex
                        items-center
                        justify-center
                        gap-2
                        bg-[#132347]
                        hover:bg-[#1A2F5C]
                        border
                        border-white/10
                        px-3
                        py-2
                        rounded-xl
                        text-white
                        text-sm
                        font-medium
                        transition-all
                        duration-200
                        w-[110px]
                      "
                  >
                    Edit Match
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      );
    }

    // ===================================
    // SINGLE PRODUCT
    // ===================================

    return (
      <div className="space-y-2">
        <div>
          <p className="font-semibold">
            {order.product_name || "Unknown Product"}
          </p>

          <p className="text-xs text-gray-400">
            SKU:
            {order.sku || "UNKNOWN"}
          </p>
        </div>

        <button
          onClick={() => {
            if (!order.order_item_id) {
              toast.error("This order has no order item.");

              return;
            }

            setSelectedItem({
              id: order.order_item_id,

              sku: order.sku,

              quantity: order.quantity,

              size: order.size,
            });

            setShowEditModal(true);
          }}
          className="
          px-3
          py-1
          rounded-lg
          bg-blue-600
          text-white
          text-xs
        "
        >
          Edit Match
        </button>
      </div>
    );
  };
  // ===================================
  // UI
  // ===================================

  return (
    <div className="max-w-[1800px] p-6 text-white">
      {/* =================================== */}
      {/* TITLE */}
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
              Orders Intelligence
            </h1>

            <p className="text-slate-400 text-xl">
              Discord operational order analytics
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
            <p className="text-slate-400 text-sm mb-2">Active Filter</p>

            <h3
              className="
              text-cyan-400
              font-black
              text-3xl
            "
            >
              {filterType === "today"
                ? "Today"
                : filterType === "yesterday"
                  ? "Yesterday"
                  : filterType === "week"
                    ? "This Week"
                    : filterType === "month"
                      ? "This Month"
                      : filterType === "custom"
                        ? "Custom"
                        : "All Time"}
            </h3>
          </div>
        </div>
      </div>

      {/* FILTERS */}

      <div
        className="
        flex
        flex-wrap
        gap-5
        mb-10
      "
      >
        {[
          { value: "today", label: "Today" },
          { value: "yesterday", label: "Yesterday" },
          { value: "week", label: "This Week" },
          { value: "month", label: "This Month" },
          { value: "all", label: "All Time" },
          { value: "custom", label: "Custom Range" },
        ].map((item) => (
          <button
            key={item.value}
            onClick={() => setFilterType(item.value)}
            className={`
            min-w-[140px]
            px-5
            py-5
            rounded-3xl
            font-bold
            text-lg
            border
            transition-all
            duration-300
            hover:scale-[1.02]

            ${
              filterType === item.value
                ? `
                  bg-cyan-500
                  text-black
                  border-cyan-400
                  shadow-lg
                  shadow-cyan-500/20
                `
                : `
                  bg-slate-900
                  text-white
                  border-slate-800
                  hover:border-slate-600
                  hover:bg-slate-800
                `
            }
          `}
          >
            {item.label}
          </button>
        ))}
      </div>

      {filterType === "custom" && (
        <div
          className="
          flex
          flex-wrap
          items-end
          gap-4
          mb-10
        "
        >
          <div>
            <p className="text-slate-300 mb-3 text-base">Start Date</p>

            <DatePicker
              selected={startDate ? new Date(startDate) : null}
              onChange={(date) => {
                if (!date) return;

                const formatted = `${date.getFullYear()}-${String(
                  date.getMonth() + 1,
                ).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;

                setStartDate(formatted);
              }}
              placeholderText="Select Start Date"
              className="
              bg-[#111C3D]
              border
              border-white/10
              rounded-2xl
              px-4
              py-3
              text-white
              outline-none
              w-[240px]
            "
            />
          </div>

          <div>
            <p className="text-slate-300 mb-3 text-base">End Date</p>

            <DatePicker
              selected={endDate ? new Date(endDate) : null}
              onChange={(date) => {
                if (!date) return;

                const formatted = `${date.getFullYear()}-${String(
                  date.getMonth() + 1,
                ).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;

                setEndDate(formatted);
              }}
              placeholderText="Select End Date"
              className="
              bg-[#111C3D]
              border
              border-white/10
              rounded-2xl
              px-4
              py-3
              text-white
              outline-none
              w-[240px]
            "
            />
          </div>

          <button
            onClick={fetchOrders}
            className="
            min-w-[180px]
            px-8
            py-4
            rounded-3xl
            bg-cyan-500
            text-black
            border
            border-cyan-400
            font-bold
            shadow-lg
            shadow-cyan-500/20
            transition-all
          "
          >
            Apply Filter
          </button>
        </div>
      )}

      {/* =================================== */}
      {/* METRICS */}
      {/* =================================== */}

      <div
        className="
    grid
    grid-cols-1
    md:grid-cols-2
    xl:grid-cols-3
    
    gap-2
    mb-2
  "
      >
        <MetricCard
          title="Total Orders"
          value={
            <>
              <style>{`
        @keyframes ultraFastGlow {
          0%, 100% { 
            opacity: 1;
            filter: drop-shadow(0 0 2px rgba(34,211,238,0.2)); 
          }
          50% { 
            opacity: 0.85;
            filter: drop-shadow(0 0 12px rgba(34,211,238,0.6)); 
          }
        }
        .hyper-pulse {
          /* 800ms is the lightning-fast speed cap for a readable text pulse */
          animation: ultraFastGlow 800ms ease-in-out infinite !important;
        }
      `}</style>
              <span className="bg-gradient-to-r from-lime-400 via-emerald-400 to-green-400 bg-clip-text text-transparent hyper-pulse">
                {totalOrders}
              </span>
            </>
          }
          icon={ShoppingCart}
        />

        <MetricCard
          title="Pending Confirmation"
          value={pendingOrders}
          color="text-yellow-400"
          icon={Clock3}
        />

        <MetricCard
          title="Active Orders"
          value={activeOrders}
          color="text-cyan-400"
          icon={Truck}
        />

        <MetricCard
          title="Delivered"
          value={completedOrders}
          color="text-lime-400"
          icon={CheckCircle2}
        />

        <MetricCard
          title="Cancelled"
          value={cancelledOrders}
          color="text-orange-400"
          icon={XCircle}
        />

        <MetricCard
          title="Returned"
          value={returnedOrders}
          color="text-red-400"
          icon={RotateCcw}
        />
      </div>

      <div className="mb-6 mt-10">
        <h2 className="text-4xl font-black text-white">
          Order Performance Overview
        </h2>

        <p className="text-slate-400 mt-2">
          Revenue, profitability and operational performance of filtered orders
        </p>
      </div>

      <div className="grid xl:grid-cols-2 gap-2 mb-10">
        <MetricCard
          title="Delivered Revenue"
          value={`Rs. ${deliveredRevenue.toLocaleString()}`}
          color="text-cyan-400"
          icon={Wallet}
        />

        <MetricCard
          title="Delivered Profit"
          value={`Rs. ${deliveredProfit.toLocaleString()}`}
          color="text-green-400"
          icon={BadgeDollarSign}
        />

        <MetricCard
          title="Cancelled Revenue Lost"
          value={`Rs. ${cancelledRevenue.toLocaleString()}`}
          color="text-red-400"
          icon={XCircle}
        />
        <MetricCard
          title="Returned Revenue Lost"
          value={`Rs. ${returnedRevenue.toLocaleString()}`}
          color="text-orange-400"
          icon={RotateCcw}
        />
        <MetricCard
          title="Total Revenue"
          value={`Rs. ${totalRevenue.toLocaleString()}`}
          color="text-cyan-400"
          icon={Wallet}
        />

        <MetricCard
          title="Avg Product Cost"
          value={`Rs. ${avgProductCost.toFixed(2)}`}
          color="text-violet-400"
          icon={BadgeDollarSign}
        />
      </div>

      {/* =================================== */}
      {/* TABLE */}
      {/* =================================== */}

      <div className="mb-6">
        <h2 className="text-4xl font-black text-white">Order Records</h2>

        <p className="text-slate-400 mt-2">
          All order transactions and profitability
        </p>
      </div>
      <div
        className="
    overflow-x-auto
    border
    rounded-3xl
    border-slate-800
    bg-gradient-to-br
    from-slate-900
    to-slate-950
    shadow-2xl
    shadow-black/30
  "
      >
        <table className="w-full min-w-[1250px]">
          <thead
            className="
    bg-[#101B38]
    text-[11px]
    uppercase
    tracking-widest
    text-slate-400
  "
          >
            <tr>
              <th className="p-5 text-left">Order ID</th>
              <th className="p-5 text-left">Source</th>
              <th className="p-5 text-left">Customer</th>
              <th className="p-5 text-left">City / Province</th>
              <th className="p-5 text-left">Product</th>
              <th className="p-5 text-left">Weight</th>
              <th className="p-5 text-left">Selling</th>
              <th className="p-5 text-left">Product Cost</th>
              <th className="p-5 text-left">Delivery</th>
              <th className="p-5 text-left">Packaging</th>
              <th className="p-5 text-left">Marketing</th>
              <th className="p-5 text-left">Total Cost</th>
              <th className="p-5 text-left">Net Profit</th>
              <th className="p-5 text-left">Margin %</th>
              <th className="p-5 text-left">Status</th>
            </tr>
          </thead>

          <tbody>
            {orders.map((order) => (
              <tr
                key={order.id}
                className="
    border-t
    border-white/10
    bg-[#081028]
    hover:bg-[#0D1735]
    transition-colors
  "
              >
                <td className="p-5 font-semibold">{order.internal_order_id}</td>

                <td className="p-5">{order.source}</td>

                <td className="p-5">
                  <div>
                    <p className="font-semibold">{order.customer_name}</p>

                    <p className="text-xs text-gray-400">
                      {order.customer_phone}
                    </p>
                  </div>
                </td>

                <td className="p-5">
                  <div>{order.city || "Not Available"}</div>

                  <div className="text-xs text-gray-400">
                    {order.province || "Not Available"}
                  </div>

                  <button
                    onClick={() => {
                      setSelectedOrderForCity(order);
                      setShowEditCityModal(true);
                    }}
                    className="
      mt-2
      px-3
      py-1
      rounded-lg
      bg-green-600
      hover:bg-green-500
      text-white
      text-xs
    "
                  >
                    Edit City
                  </button>
                </td>

                <td className="p-5">{renderProducts(order)}</td>

                <td className="p-5">{order.weight_kg} KG</td>

                <td className="p-5">Rs. {order.selling_price}</td>

                <td className="p-5">Rs. {order.product_cost}</td>

                <td className="p-5">Rs. {order.delivery_cost}</td>

                <td className="p-5">
                  <div>
                    <div>Rs. {order.packaging_cost}</div>

                    {order.products?.length > 1 && (
                      <div className="text-xs text-gray-400 mt-1">
                        50 × {order.products.length}
                      </div>
                    )}
                  </div>
                </td>

                <td className="p-5">Rs. {order.marketing_cost}</td>

                <td className="p-5 font-semibold text-rose-500 drop-shadow-[0_0_10px_rgba(251,113,133,0.35)]">
                  Rs. {order.total_cost}
                </td>

                <td
                  className={`
    p-5
    font-bold

    ${
      Number(order.net_profit) >= 0
        ? "text-green-400 drop-shadow-[0_0_14px_rgba(134,239,172,0.45)]"
        : "text-rose-500 drop-shadow-[0_0_10px_rgba(251,113,133,0.35)]"
    }
  `}
                >
                  Rs. {order.net_profit}
                </td>

                <td className="p-5">{order.profit_margin}%</td>

                <td className="p-5">
                  <span
                    className={`
                        px-4
                        py-2
                        rounded-xl
                        text-xs
                        font-semibold

                        ${
                          order.status === "DELIVERED"
                            ? "bg-green-500/20 text-green-400"
                            : order.status === "CONFIRMED"
                              ? "bg-cyan-500/20 text-cyan-400"
                              : order.status === "CANCELLED"
                                ? "bg-red-500/20 text-red-400"
                                : order.status === "RETURNED"
                                  ? "bg-orange-500/20 text-orange-400"
                                  : "bg-yellow-500/20 text-yellow-400"
                        }
                      `}
                  >
                    {order.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showEditModal && selectedItem && (
        <EditMatchModal
          item={selectedItem}
          onClose={() => {
            setShowEditModal(false);

            setSelectedItem(null);
          }}
          onUpdated={async () => {
            await fetchOrders();

            setShowEditModal(false);

            setSelectedItem(null);
          }}
        />
      )}

      {showEditCityModal && selectedOrderForCity && (
        <EditCityModal
          order={selectedOrderForCity}
          onClose={() => setShowEditCityModal(false)}
          onUpdated={() => {
            fetchOrders();
          }}
        />
      )}
    </div>
  );
}

function MetricCard({ title, value, color = "", icon: Icon }) {
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
      <div className="flex items-center gap-5">
        {Icon && (
          <div
            className="
            w-12
            h-12
            rounded-2xl
            bg-slate-800
            flex
            items-center
            justify-center
            border
            border-slate-700
          "
          >
            <Icon size={25} className={color} />
          </div>
        )}

        <p className="text-slate-300 text-lg font-medium">{title}</p>
      </div>

      <h2
        className={`
          truncate
          text-3xl
          xl:text-4xl
          font-black
          ${color}
        `}
      >
        {value}
      </h2>
    </div>
  );
}
