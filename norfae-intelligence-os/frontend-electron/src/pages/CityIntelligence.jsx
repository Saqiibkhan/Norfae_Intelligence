import { useEffect, useState } from "react";

import { toast } from "sonner";

import api from "../lib/api";

import { Input } from "@/components/ui/input";

function CityIntelligence() {
  const [cities, setCities] = useState([]);

  const [search, setSearch] = useState("");

  const [loading, setLoading] = useState(false);

  const [sortField, setSortField] = useState("profit");

  const [sortDirection, setSortDirection] = useState("desc");

  const [intelligenceFilter, setIntelligenceFilter] = useState("all");

  // ===================================
  // FETCH CITIES INTELLIGENCE
  // ===================================

  async function fetchCityIntelligence() {
    try {
      setLoading(true);

      const response = await api.get("/city-intelligence");

      console.log("CITY INTELLIGENCE:", response.data);

      // ===============================
      // BACKEND RETURNS ARRAY
      // ===============================

      setCities(response.data.cities || []);
    } catch (error) {
      console.log("CITY INTELLIGENCE ERROR:", error);
      toast.error("Failed to load city intelligence");
    } finally {
      setLoading(false);
    }
  }

  // ===================================
  // INITIAL LOAD
  // ===================================

  useEffect(() => {
    const loadData = async () => {
      await fetchCityIntelligence();
    };

    loadData();
  }, []);

  // ===================================
  // FILTER Cities
  // ===================================

  const filteredCities = Array.isArray(cities)
    ? cities.filter((city) => {
        // ===========================
        // SEARCH FILTER
        // ===========================

        const matchesSearch =
          (city.city || "").toLowerCase().includes(search.toLowerCase()) ||
          (city.province || "").toLowerCase().includes(search.toLowerCase());

        if (!matchesSearch) {
          return false;
        }

        // ===========================
        // INTELLIGENCE FILTERS
        // ===========================

        if (intelligenceFilter === "top_profit") {
          return Number(city.profit || 0) > 20000;
        }
        if (intelligenceFilter === "high_returns") {
          return Number(city.returned || 0) >= 5;
        }

        if (intelligenceFilter === "high_cancels") {
          return Number(city.cancelled || 0) >= 20;
        }

        if (intelligenceFilter === "elite_cities") {
          return city.performance_status === "elite";
        }

        if (intelligenceFilter === "risky_cities") {
          return city.performance_status === "risky";
        }

        return true;
      })
    : [];

  const totalCities = filteredCities.length;

  const totalRevenue = filteredCities.reduce(
    (sum, product) => sum + Number(product.revenue || 0),
    0,
  );

  const totalProfit = filteredCities.reduce(
    (sum, product) => sum + Number(product.profit || 0),
    0,
  );

  const bestCity = [...filteredCities].sort(
    (a, b) => Number(b.profit || 0) - Number(a.profit || 0),
  )[0];

  const highestReturnCity = [...filteredCities].sort(
    (a, b) => Number(b.returned || 0) - Number(a.returned || 0),
  )[0];
  const sortedCities = [...filteredCities].sort((a, b) => {
    let aValue = a[sortField];

    let bValue = b[sortField];

    // ===========================
    // STRING SORT
    // ===========================

    if (typeof aValue === "string") {
      aValue = aValue.toLowerCase();

      bValue = bValue.toLowerCase();

      if (sortDirection === "asc") {
        return aValue.localeCompare(bValue);
      }

      return bValue.localeCompare(aValue);
    }

    // ===========================
    // NUMBER SORT
    // ===========================

    aValue = Number(aValue || 0);

    bValue = Number(bValue || 0);

    if (sortDirection === "asc") {
      return aValue - bValue;
    }

    return bValue - aValue;
  });

  function handleSort(field) {
    if (sortField === field) {
      setSortDirection(sortDirection === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);

      setSortDirection("desc");
    }
  }

  function getSortIndicator(field) {
    if (sortField !== field) {
      return "";
    }

    return sortDirection === "asc" ? " ↑" : " ↓";
  }

  return (
    <div
      className="
      max-w-[1800px]
      p-6
    "
    >
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
              City Intelligence
            </h1>

            <p className="text-slate-400 text-xl">
              City performance analytics and delivery intelligence
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
        px-9
        py-8
        min-w-[210px]
      "
          >
            <p className="text-slate-400 text-sm mb-2">Cities Analyzed</p>

            <h3
              className="
          text-cyan-400
          font-black
          text-4xl
        "
            >
              {totalCities}
            </h3>
          </div>
        </div>
      </div>

      {/* =================================== */}
      {/* SEARCH + FILTERS */}
      {/* =================================== */}

      <div
        className="
    mb-8
    flex
    flex-col
    gap-6
  "
      >
        <Input
          placeholder="Search by City or Province..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="
      bg-[#111C3D]
      border-white/10
      text-white
      h-14
      rounded-2xl
      max-w-[500px]
    "
        />

        <div
          className="
      flex
      flex-wrap
      gap-3
    "
        >
          {[
            {
              key: "all",
              label: "All",
            },

            {
              key: "top_profit",
              label: "Profitable Cities",
            },

            {
              key: "high_returns",
              label: "High Returns",
            },

            {
              key: "high_cancels",
              label: "High Cancels",
            },

            {
              key: "elite_cities",
              label: "Elite Cities",
            },
            {
              key: "risky_cities",
              label: "Risky Cities",
            },
          ].map((filter) => (
            <button
              key={filter.key}
              onClick={() => setIntelligenceFilter(filter.key)}
              className={`
          min-w-[180px]
          px-8
          py-4
          rounded-2xl
          font-bold
          text-sm
          transition-all
          border

          ${
            intelligenceFilter === filter.key
              ? `
                bg-cyan-500
                text-black
                border-cyan-400
                shadow-lg
                shadow-cyan-500/20
              `
              : `
                bg-slate-900
                border-slate-800
                text-slate-400
                hover:border-cyan-400/20
                hover:text-cyan-200
              `
          }
        `}
            >
              {filter.label}
            </button>
          ))}
        </div>
      </div>

      {/* =================================== */}
      {/* METRIC CARDS */}
      {/* =================================== */}

      <div
        className="
    grid
    grid-cols-1
    md:grid-cols-2
    xl:grid-cols-3
    gap-4
    mb-12
  "
      >
        <MetricCard title="Cities" value={totalCities} color="text-white" />

        <MetricCard
          title="Revenue"
          value={`Rs. ${totalRevenue.toLocaleString()}`}
          color="text-cyan-400"
        />

        <MetricCard
          title="Profit"
          value={`Rs. ${totalProfit.toLocaleString()}`}
          color="text-lime-400"
        />

        <MetricCard title="Best City" value={bestCity?.city || "N/A"} />

        <MetricCard
          title="Highest Returns"
          value={highestReturnCity?.city || "N/A"}
        />
      </div>

      {/* =================================== */}
      {/* LOADING */}
      {/* =================================== */}

      {loading && (
        <div
          className="
            text-cyan-400
            text-lg
            mb-6
          "
        >
          Loading city intelligence...
        </div>
      )}

      {/* =================================== */}
      {/* EMPTY STATE */}
      {/* =================================== */}

      {!loading && filteredCities.length === 0 && (
        <div
          className="
            bg-slate-900
            border
            border-slate-800
            rounded-3xl
            p-10
            text-center
            text-slate-400
          "
        >
          No cities match current filters
        </div>
      )}

      {/* =================================== */}
      {/* TABLE */}
      {/* =================================== */}

      {filteredCities.length > 0 && (
        <div
          className="
            overflow-x-auto
            bg-gradient-to-br
            from-slate-900
            to-slate-950
            border
            border-slate-800
            rounded-3xl
          "
        >
          <table
            className="
              w-full
              text-left
              min-w-[1800px]
            "
          >
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
                <th
                  onClick={() => handleSort("city")}
                  className={`
    p-5
    cursor-pointer
    select-none
    transition-all
    hover:text-cyan-300

    ${sortField === "city" ? "text-cyan-300" : "text-slate-400"}
  `}
                >
                  City
                  {getSortIndicator("city")}
                </th>

                <th
                  onClick={() => handleSort("province")}
                  className={`
    p-5
    cursor-pointer
    select-none
    transition-all
    hover:text-cyan-300

    ${sortField === "province" ? "text-cyan-300" : "text-slate-400"}
  `}
                >
                  Province
                  {getSortIndicator("province")}
                </th>

                <th
                  onClick={() => handleSort("performance_status")}
                  className={`
    p-5
    cursor-pointer
    select-none
    transition-all
    hover:text-cyan-300

    ${sortField === "performance_status" ? "text-cyan-300" : "text-slate-400"}
  `}
                >
                  Status
                  {getSortIndicator("performance_status")}
                </th>

                <th
                  onClick={() => handleSort("orders")}
                  className={`
    p-5
    cursor-pointer
    select-none
    transition-all
    hover:text-cyan-300

    ${sortField === "orders" ? "text-cyan-300" : "text-slate-400"}
  `}
                >
                  Orders
                  {getSortIndicator("orders")}
                </th>

                <th
                  onClick={() => handleSort("delivered")}
                  className={`
    p-5
    cursor-pointer
    select-none
    transition-all
    hover:text-cyan-300

    ${sortField === "delivered" ? "text-cyan-300" : "text-slate-400"}
  `}
                >
                  Delivered
                  {getSortIndicator("delivered")}
                </th>

                <th
                  onClick={() => handleSort("cancelled")}
                  className={`
    p-5
    cursor-pointer
    select-none
    transition-all
    hover:text-cyan-300

    ${sortField === "cancelled" ? "text-cyan-300" : "text-slate-400"}
  `}
                >
                  Cancelled
                  {getSortIndicator("cancelled")}
                </th>

                <th
                  onClick={() => handleSort("returned")}
                  className={`
    p-5
    cursor-pointer
    select-none
    transition-all
    hover:text-cyan-300

    ${sortField === "returned" ? "text-cyan-300" : "text-slate-400"}
  `}
                >
                  Returned
                  {getSortIndicator("returned")}
                </th>

                <th
                  onClick={() => handleSort("revenue")}
                  className={`
    p-5
    cursor-pointer
    select-none
    transition-all
    hover:text-cyan-300

    ${sortField === "revenue" ? "text-cyan-300" : "text-slate-400"}
  `}
                >
                  Revenue
                  {getSortIndicator("revenue")}
                </th>

                <th
                  onClick={() => handleSort("profit")}
                  className={`
    p-5
    cursor-pointer
    select-none
    transition-all
    hover:text-cyan-300

    ${sortField === "profit" ? "text-cyan-300" : "text-slate-400"}
  `}
                >
                  Profit
                  {getSortIndicator("profit")}
                </th>

                <th
                  onClick={() => handleSort("avg_delivery_cost")}
                  className={`
    p-5
    cursor-pointer
    select-none
    transition-all
    hover:text-cyan-300

    ${sortField === "avg_delivery_cost" ? "text-cyan-300" : "text-slate-400"}
  `}
                >
                  Avg Delivery Cost
                  {getSortIndicator("avg_delivery_cost")}
                </th>

                <th
                  onClick={() => handleSort("success_rate")}
                  className={`
    p-5
    cursor-pointer
    select-none
    transition-all
    hover:text-cyan-300

    ${sortField === "success_rate" ? "text-cyan-300" : "text-slate-400"}
  `}
                >
                  Success Rate
                  {getSortIndicator("success_rate")}
                </th>

                <th
                  onClick={() => handleSort("profit_margin")}
                  className={`
    p-5
    cursor-pointer
    select-none
    transition-all
    hover:text-cyan-300

    ${sortField === "profit_margin" ? "text-cyan-300" : "text-slate-400"}
  `}
                >
                  Margin %{getSortIndicator("profit_margin")}
                </th>

                <th
                  onClick={() => handleSort("loss_rate")}
                  className={`
    p-5
    cursor-pointer
    select-none
    transition-all
    hover:text-cyan-300

    ${sortField === "loss_rate" ? "text-cyan-300" : "text-slate-400"}
  `}
                >
                  Loss Rate
                  {getSortIndicator("loss_rate")}
                </th>

                <th
                  onClick={() => handleSort("revenue_per_order")}
                  className={`
    p-5
    cursor-pointer
    select-none
    transition-all
    hover:text-cyan-300

    ${sortField === "revenue_per_order" ? "text-cyan-300" : "text-slate-400"}
  `}
                >
                  Revenue / Order
                  {getSortIndicator("revenue_per_order")}
                </th>

                <th
                  onClick={() => handleSort("profit_per_order")}
                  className={`
    p-5
    cursor-pointer
    select-none
    transition-all
    hover:text-cyan-300

    ${sortField === "profit_per_order" ? "text-cyan-300" : "text-slate-400"}
  `}
                >
                  Profit / Order
                  {getSortIndicator("profit_per_order")}
                </th>
              </tr>
            </thead>

            <tbody>
              {sortedCities.map((product, index) => (
                <tr
                  key={`${product.city}-${product.province}-${index}`}
                  className="
                          border-b
                          border-slate-800
                          hover:bg-[#0D1735]
                          transition-all
                        "
                >
                  {/* City */}

                  <td
                    className="
                          p-5
                          text-cyan-400
                          font-semibold
                        "
                  >
                    {product.city || "UNKNOWN"}
                  </td>

                  {/* CITIES */}

                  <td
                    className="
    p-5
    text-white
    font-semibold
  "
                  >
                    <div>
                      {product.province}

                      <div
                        className="
      flex
      gap-2
      mt-2
      flex-wrap
    "
                      >
                        {product.city === bestCity?.city && (
                          <span
                            className="
      px-2
      py-1
      rounded-lg
      bg-lime-400/10
      text-lime-300
      text-[10px]
      font-bold
      tracking-wide
    "
                          >
                            TOP CITY
                          </span>
                        )}

                        {product.performance_status === "elite" && (
                          <span
                            className="
      px-2
      py-1
      rounded-lg
      bg-cyan-400/10
      text-cyan-300
      text-[10px]
      font-bold
    "
                          >
                            ELITE
                          </span>
                        )}

                        {Number(product.returned || 0) >= 5 && (
                          <span
                            className="
            px-2
            py-1
            rounded-lg
            bg-amber-400/10
            text-amber-300
            text-[10px]
            font-bold
            tracking-wide
          "
                          >
                            HIGH RETURNS
                          </span>
                        )}

                        {Number(product.cancelled || 0) >= 20 && (
                          <span
                            className="
            px-2
            py-1
            rounded-lg
            bg-rose-400/10
            text-rose-300
            text-[10px]
            font-bold
            tracking-wide
          "
                          >
                            HIGH CANCELS
                          </span>
                        )}
                      </div>
                    </div>
                  </td>

                  {/* PERFORMANCE STATUS */}

                  <td className="p-5">
                    <span
                      className={`

      px-4
      py-2
      rounded-2xl
      text-xs
      font-black
      uppercase
      tracking-wider
      border

      ${
        product.performance_status === "elite"
          ? `
            bg-lime-400/10
            text-lime-300
            border-lime-400/30
            shadow-lg
            shadow-lime-500/10
          `
          : product.performance_status === "strong"
            ? `
            bg-cyan-400/10
            text-cyan-300
            border-cyan-400/30
            shadow-lg
            shadow-cyan-500/10
          `
            : product.performance_status === "risky"
              ? `
            bg-amber-400/10
            text-amber-300
            border-amber-400/30
            shadow-lg
            shadow-amber-500/10
          `
              : product.performance_status === "loss"
                ? `
            bg-rose-400/10
            text-rose-300
            border-rose-400/30
            shadow-lg
            shadow-rose-500/10
          `
                : `
            bg-slate-400/10
            text-slate-300
            border-slate-400/20
          `
      }
    `}
                    >
                      {product.performance_status}
                    </span>
                  </td>

                  {/* ORDERS */}

                  <td
                    className="
                          p-5
                          text-slate-300
                        "
                  >
                    {product.orders || 0}
                  </td>

                  {/* DELIVERED */}

                  <td
                    className="
                          p-5
                          text-green-400
                          font-semibold
                        "
                  >
                    {product.delivered || 0}
                  </td>

                  {/* CANCELLED */}

                  <td
                    className="
                          p-5
                          text-red-400
                          font-semibold
                        "
                  >
                    {product.cancelled || 0}
                  </td>

                  {/* RETURNED */}

                  <td
                    className="
                          p-5
                          text-yellow-400
                          font-semibold
                        "
                  >
                    {product.returned || 0}
                  </td>

                  {/* REVENUE */}

                  <td
                    className="
                          p-5
                          text-cyan-400
                          font-bold
                        "
                  >
                    Rs. {Number(product.revenue || 0).toLocaleString()}
                  </td>

                  {/* PROFIT */}

                  <td
                    className="
                          p-5
                          text-green-400
                          font-bold
                        "
                  >
                    Rs. {Number(product.profit || 0).toLocaleString()}
                  </td>

                  {/* AVG DELIVERY COST */}

                  <td
                    className="
    p-5
    text-orange-300
    font-bold
  "
                  >
                    Rs.{" "}
                    {Number(product.avg_delivery_cost || 0).toLocaleString()}
                  </td>

                  {/* SUCCESS RATE */}

                  <td
                    className="
                          p-5
                          text-violet-400
                          font-bold
                        "
                  >
                    {product.success_rate || 0}%
                  </td>

                  {/* PROFIT MARGIN */}

                  <td
                    className="
    p-5
    text-emerald-300
    font-bold
  "
                  >
                    {product.profit_margin || 0}%
                  </td>

                  {/* LOSS RATE */}

                  <td
                    className={`
    p-5
    font-bold

    ${Number(product.loss_rate || 0) >= 40 ? "text-rose-400" : "text-amber-300"}
  `}
                  >
                    {product.loss_rate || 0}%
                  </td>

                  {/* REVENUE PER ORDER */}

                  <td
                    className="
    p-5
    text-cyan-300
    font-bold
  "
                  >
                    Rs.{" "}
                    {Number(product.revenue_per_order || 0).toLocaleString()}
                  </td>

                  {/* PROFIT PER ORDER */}

                  <td
                    className={`
    p-5
    font-bold

    ${
      Number(product.profit_per_order || 0) >= 0
        ? "text-lime-300"
        : "text-rose-400"
    }
  `}
                  >
                    Rs. {Number(product.profit_per_order || 0).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function MetricCard({ title, value, color = "" }) {
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
      <p className="text-slate-400 text-lg">{title}</p>

      <h2
        className={`
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

export default CityIntelligence;
