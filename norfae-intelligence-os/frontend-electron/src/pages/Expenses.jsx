import { useEffect, useState, useCallback } from "react";

import api from "../services/api";

import { Button } from "@/components/ui/button";

import { Input } from "@/components/ui/input";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

import DatePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";
import { toast } from "sonner";

import {
  Megaphone,
  Settings,
  Fuel,
  Home,
  Wallet,
  Receipt,
  Plane,
  Building2,
  Monitor,
  Wrench,
  Repeat,
  CircleDollarSign,
  Users,
} from "lucide-react";

export default function Expenses() {
  // ===================================
  // STATE
  // ===================================

  const [expenses, setExpenses] = useState([]);

  const [loading, setLoading] = useState(true);

  const [filter, setFilter] = useState("today");

  const [customStartDate, setCustomStartDate] = useState(null);

  const [customEndDate, setCustomEndDate] = useState(null);

  const [openModal, setOpenModal] = useState(false);

  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);

  const [selectedExpense, setSelectedExpense] = useState(null);

  const [formData, setFormData] = useState({
    title: "",

    amount: "",

    category: "",

    payment_method: "",

    notes: "",

    is_recurring: false,

    recurring_cycle: "",

    created_at: new Date().toISOString().slice(0, 16),
  });

  const categoryIcons = {
    marketing: Megaphone,
    operations: Settings,
    salary: Users,

    rent: Home,
    fuel: Fuel,
    utility: Wrench,
    software: Monitor,
    office: Building2,
    tax: Receipt,
    travel: Plane,
    other: CircleDollarSign,
    recurring: Repeat,
  };

  const categoryColors = {
    salary: "text-green-400",
    rent: "text-cyan-400",
    fuel: "text-yellow-400",
    utility: "text-purple-400",
    software: "text-pink-400",
    office: "text-blue-400",
    tax: "text-red-400",
    travel: "text-sky-400",
    other: "text-gray-300",
  };

  // ===================================
  // FETCH EXPENSES
  // ===================================

  const fetchExpenses = useCallback(async () => {
    try {
      const response = await api.get("/expenses/", {
        params: {
          filter_type: filter,
          start_date: customStartDate
            ? customStartDate.toISOString().split("T")[0]
            : null,
          end_date: customEndDate
            ? customEndDate.toISOString().split("T")[0]
            : null,
        },
      });

      setExpenses(Array.isArray(response.data) ? response.data : []);
    } catch (error) {
      console.error("Expense fetch failed:", error);
    } finally {
      setLoading(false);
    }
  }, [filter, customStartDate, customEndDate]);

  useEffect(() => {
    const loadExpenses = async () => {
      await fetchExpenses();
    };

    loadExpenses();
  }, [fetchExpenses]);

  // ===================================
  // CREATE EXPENSE
  // ===================================

  const createExpense = async () => {
    try {
      await api.post("/expenses/", {
        ...formData,

        amount: Number(formData.amount),

        created_at: new Date(formData.created_at).toISOString(),
      });

      await fetchExpenses();

      toast.success("Expense Added Successfully");

      setOpenModal(false);

      setFormData({
        title: "",

        amount: "",

        category: "",

        payment_method: "",

        notes: "",

        is_recurring: false,

        recurring_cycle: "",

        created_at: new Date().toISOString().slice(0, 16),
      });
    } catch (error) {
      console.error(error);

      toast.error("Failed to create expense");
    }
  };

  // ===================================
  // DELETE EXPENSE
  // ===================================

  const deleteExpense = async (expenseId) => {
    try {
      await api.delete(`/expenses/${expenseId}`);

      setExpenses((prev) => prev.filter((expense) => expense.id !== expenseId));
      toast.success("Expense Deleted Successfully");
    } catch (error) {
      console.error(error);

      toast.error("Failed to delete expense");
    }
  };

  // ===================================
  // METRICS
  // ===================================

  const totalExpenses = expenses.reduce(
    (sum, expense) => sum + Number(expense.amount || 0),
    0,
  );

  const marketingSpend = expenses
    .filter(
      (expense) =>
        expense.category?.toLowerCase() === "marketing" &&
        expense.source !== "meta",
    )
    .reduce((sum, expense) => sum + Number(expense.amount || 0), 0);

  const metaSpend = expenses
    .filter((expense) => expense.source === "meta")
    .reduce((sum, expense) => sum + Number(expense.amount || 0), 0);
  const operationalSpend = expenses
    .filter((expense) => expense.category?.toLowerCase() === "operations")
    .reduce((sum, expense) => sum + Number(expense.amount || 0), 0);

  const recurringExpenses = expenses.filter(
    (expense) => expense.is_recurring,
  ).length;

  const categoryTotals = expenses.reduce((acc, expense) => {
    const category = (expense.category || "Other").trim().toLowerCase();

    // Already shown in fixed cards
    if (category === "marketing") return acc;
    if (category === "operations") return acc;

    // Meta has its own card
    if (expense.source === "meta") return acc;

    if (!acc[category]) {
      acc[category] = 0;
    }

    acc[category] += Number(expense.amount || 0);

    return acc;
  }, {});
  // ===================================
  // LOADING
  // ===================================

  if (loading) {
    return (
      <div className="p-6 animate-pulse">
        <div className="h-12 w-72 rounded bg-slate-800 mb-8"></div>

        <div className="grid grid-cols-2 gap-4 mb-8">
          {[1, 2, 3, 4].map((item) => (
            <div
              key={item}
              className="
              h-40
              rounded-3xl
              bg-slate-900
            "
            />
          ))}
        </div>

        <div
          className="
          h-96
          rounded-3xl
          bg-slate-900
        "
        />
      </div>
    );
  }

  // ===================================
  // UI
  // ===================================

  return (
    <div className="max-w-[1800px] p-6 text-white">
      {/* HEADER */}

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
              Expenses
            </h1>

            <p className="text-slate-400 text-xl">
              Expense tracking and operational analytics
            </p>
          </div>

          <div className="flex items-end gap-4">
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
                {filter === "today"
                  ? "Today"
                  : filter === "yesterday"
                    ? "Yesterday"
                    : filter === "week"
                      ? "This Week"
                      : filter === "month"
                        ? "This Month"
                        : filter === "custom"
                          ? "Custom Range"
                          : "All Time"}
              </h3>
            </div>
          </div>
        </div>
      </div>

      {/* FILTERS */}

      <div
        className="
        flex
        flex-wrap
        gap-4
        mb-8
      "
      >
        {["today", "yesterday", "week", "month", "all", "custom"].map(
          (type) => (
            <Button
              key={type}
              onClick={() => setFilter(type)}
              className={`
              px-8
              py-8
              rounded-2xl
              border
              transition-all
              font-semibold
              text-lg


            ${
              filter === type
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
              {type === "today"
                ? "Today"
                : type === "yesterday"
                  ? "Yesterday"
                  : type === "week"
                    ? "This Week"
                    : type === "month"
                      ? "This Month"
                      : type === "custom"
                        ? "Custom Range"
                        : "All Time"}
            </Button>
          ),
        )}
      </div>

      {filter === "custom" && (
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
              selected={customStartDate}
              onChange={(date) => setCustomStartDate(date)}
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
              selected={customEndDate}
              onChange={(date) => setCustomEndDate(date)}
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
            onClick={fetchExpenses}
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
  "
          >
            Apply Filter
          </button>
        </div>
      )}

      {/* METRICS */}

      <div
        className="
        grid
        grid-cols-1
        md:grid-cols-2
        xl:grid-cols-3
        gap-2
        mb-10
      "
      >
        <MetricCard
          title="Total Expenses"
          value={`Rs. ${totalExpenses.toLocaleString()}`}
          color="text-red-400"
          icon={Wallet}
        />

        <MetricCard
          title="Marketing Spend"
          value={`Rs. ${marketingSpend.toLocaleString()}`}
          color="text-pink-400"
          icon={Megaphone}
        />

        <MetricCard
          title="Meta Spend"
          value={`Rs. ${metaSpend.toLocaleString()}`}
          color="text-cyan-400"
          icon={CircleDollarSign}
        />

        <MetricCard
          title="Operations Spend"
          value={`Rs. ${operationalSpend.toLocaleString()}`}
          color="text-yellow-400"
          icon={Settings}
        />

        <MetricCard
          title="Recurring Expenses"
          value={recurringExpenses}
          color="text-cyan-400"
          icon={Repeat}
        />

        {Object.entries(categoryTotals).map(([category, amount]) => (
          <MetricCard
            key={category}
            title={`${category} Spend`}
            value={`Rs. ${amount.toLocaleString()}`}
            color={categoryColors[category] || "text-cyan-400"}
            icon={categoryIcons[category]}
          />
        ))}
      </div>

      {/* TABLE */}

      <div
        className="
    flex
    flex-col
    md:flex-row
    md:items-center
    md:justify-between
    gap-4
    mb-6
  "
      >
        <div>
          <h2
            className="
        text-4xl
        font-black
        text-white
      "
          >
            Expense Records
          </h2>

          <p className="text-slate-400 mt-2">All expense transactions</p>
        </div>

        <Dialog open={openModal} onOpenChange={setOpenModal}>
          <DialogTrigger asChild>
            <Button
              className="
          bg-cyan-500
          hover:bg-cyan-400
          text-black
          font-black
          rounded-2xl
          px-6
          py-8
          text-lg
          min-w-[180px]
        "
            >
              Add Expense
            </Button>
          </DialogTrigger>

          <DialogContent className="bg-[#081028] border border-white/10 text-white max-w-2xl">
            <DialogHeader>
              <DialogTitle className="text-2xl font-black">
                Create Expense
              </DialogTitle>
            </DialogHeader>

            <div className="grid grid-cols-2 gap-4 mt-4">
              <Input
                placeholder="Expense Title"
                value={formData.title}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    title: e.target.value,
                  })
                }
                className="bg-[#111C3D] border-white/10"
              />

              <Input
                placeholder="Amount"
                type="number"
                value={formData.amount}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    amount: e.target.value,
                  })
                }
                className="bg-[#111C3D] border-white/10"
              />

              <select
                value={formData.category}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    category: e.target.value,
                  })
                }
                className="
                  bg-[#111C3D]
                  border
                  border-white/10
                  rounded-md
                  px-3
                  py-2
                  text-white
                "
              >
                <option value="">Select Category</option>

                <option value="Marketing">Marketing</option>

                <option value="Operations">Operations</option>

                <option value="Fuel">Fuel</option>

                <option value="Utility">Utility</option>

                <option value="Salary">Salary</option>

                <option value="Rent">Rent</option>

                <option value="Software">Software</option>

                <option value="Tax">Tax</option>

                <option value="Travel">Travel</option>

                <option value="Office">Office</option>

                <option value="Other">Other</option>
              </select>

              <select
                value={formData.payment_method}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    payment_method: e.target.value,
                  })
                }
                className="
                  bg-[#111C3D]
                  border
                  border-white/10
                  rounded-md
                  px-3
                  py-2
                  text-white
                "
              >
                <option value="">Select Payment Method</option>

                <option value="Cash">Cash</option>

                <option value="Bank Deposit">Bank Deposit</option>

                <option value="Online Banking">Online Banking</option>

                <option value="NayaPay">NayaPay</option>

                <option value="EasyPaisa">EasyPaisa</option>

                <option value="JazzCash">JazzCash</option>

                <option value="Debit Card">Debit Card</option>

                <option value="Cheque">Cheque</option>

                <option value="Other">Other</option>
              </select>

              <Input
                type="datetime-local"
                value={formData.created_at}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    created_at: e.target.value,
                  })
                }
                className="bg-[#111C3D] border-white/10"
              />
            </div>

            <textarea
              placeholder="Notes"
              value={formData.notes}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  notes: e.target.value,
                })
              }
              className="
                  mt-4
                  w-full
                  bg-[#111C3D]
                  border
                  border-white/10
                  rounded-xl
                  p-4
                  text-white
                  outline-none
                "
            />

            <div className="flex items-center gap-3 mt-4">
              <input
                type="checkbox"
                checked={formData.is_recurring}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    is_recurring: e.target.checked,
                  })
                }
              />

              <span className="text-sm">Recurring Expense</span>
            </div>

            {formData.is_recurring && (
              <select
                value={formData.recurring_cycle}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    recurring_cycle: e.target.value,
                  })
                }
                className="
                  mt-4
                  w-full
                  bg-[#111C3D]
                  border
                  border-white/10
                  rounded-xl
                  p-3
                  text-white
                "
              >
                <option value="">Select Cycle</option>

                <option value="Daily">Daily</option>

                <option value="Weekly">Weekly</option>

                <option value="Monthly">Monthly</option>

                <option value="Quarterly">Quarterly</option>

                <option value="Yearly">Yearly</option>
              </select>
            )}

            <Button
              onClick={createExpense}
              className="
                  mt-6
                  bg-cyan-500
                  hover:bg-cyan-400
                  text-black
                  font-bold
                  rounded-xl
                "
            >
              Create Expense
            </Button>
          </DialogContent>
        </Dialog>

        <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
          <DialogContent className="bg-[#081028] border border-white/10 text-white max-w-md">
            <DialogHeader>
              <DialogTitle className="text-2xl font-black">
                Delete Expense
              </DialogTitle>
            </DialogHeader>

            <p className="text-slate-300">
              Are you sure you want to delete
              <span className="font-bold text-white">
                {" "}
                {selectedExpense?.title}
              </span>
              ?
            </p>

            <div className="flex justify-end gap-3 mt-6">
              <Button
                variant="outline"
                onClick={() => setDeleteDialogOpen(false)}
              >
                Cancel
              </Button>

              <Button
                className="bg-red-500 hover:bg-red-600"
                onClick={async () => {
                  await deleteExpense(selectedExpense.id);
                  setDeleteDialogOpen(false);
                }}
              >
                Delete
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <div
        className="
        bg-gradient-to-br
        from-slate-900
        to-slate-950
        rounded-3xl
        border
        border-slate-800
        overflow-x-auto
      "
      >
        <table className="w-full">
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
              <th className="p-5 text-left">Expense</th>

              <th className="p-5 text-left">Category</th>

              <th className="p-5 text-left">Source</th>

              <th className="p-5 text-left">Payment</th>

              <th className="p-5 text-left">Amount</th>

              <th className="p-5 text-left">Recurring</th>

              <th className="p-5 text-left">Date</th>
              <th className="p-5 text-left">Action</th>
            </tr>
          </thead>

          <tbody>
            {expenses.map((expense) => (
              <tr
                key={expense.id}
                className="
  border-t
  border-white/10
  bg-[#081028]
  hover:bg-[#0D1735]
  transition-colors
"
              >
                <td className="p-5 font-semibold whitespace-nowrap">
                  {expense.title}
                </td>

                <td className="p-5">
                  <span
                    className={`
                      px-3
                      py-1
                      rounded-xl
                      text-xs
                      font-bold
                      ${getCategoryBadge(expense.category)}
                    `}
                  >
                    {expense.category || "N/A"}
                  </span>
                </td>

                <td className="p-5">
                  <span
                    className={
                      expense.source === "meta"
                        ? "text-cyan-400 font-bold"
                        : "text-slate-300"
                    }
                  >
                    {expense.source === "meta"
                      ? "FB"
                      : expense.source || "manual"}
                  </span>
                </td>

                <td className="p-5">
                  <span
                    className={`
                    inline-flex
                    whitespace-nowrap
                    px-3
                    py-1
                    rounded-xl
                    text-xs
                    font-bold
                    ${getPaymentBadge(expense.payment_method)}
                  `}
                  >
                    {expense.payment_method || "-"}
                  </span>
                </td>

                <td className="p-5 text-rose-400 drop-shadow-[0_0_12px_rgba(251,113,133,0.35)] font-bold">
                  Rs. {Number(expense.amount).toLocaleString()}
                </td>

                <td className="p-5">
                  {expense.is_recurring ? (
                    <span className="px-3 py-1 rounded-xl bg-orange-500/20 text-orange-400 text-xs font-bold">
                      {expense.recurring_cycle || "Recurring"}
                    </span>
                  ) : (
                    <span className="text-slate-500">No</span>
                  )}
                </td>

                <td className="p-5">
                  {new Date(
                    expense.expense_date || expense.created_at,
                  ).toLocaleDateString()}
                </td>

                <td className="p-5">
                  {expense.source === "meta" ? (
                    <span className="text-cyan-400 font-bold">AUTO</span>
                  ) : (
                    <button
                      onClick={() => {
                        setSelectedExpense(expense);
                        setDeleteDialogOpen(true);
                      }}
                      className="
                        px-4
                        py-2
                        rounded-xl
                        bg-red-500/10
                        border
                        border-red-500/20
                        text-red-400
                        text-xs
                        font-bold
                        hover:bg-red-500/20
                        transition-all
                      "
                    >
                      DELETE
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
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
      "
    >
      <div className="flex items-center gap-4 mb-6">
        {Icon && (
          <div className="w-16 h-16 rounded-full bg-slate-800 flex items-center justify-center">
            <Icon className={color} size={30} />
          </div>
        )}

        <p className="text-slate-300 text-lg font-medium">{title}</p>
      </div>

      <h2 className={`text-3xl font-black ${color}`}>{value}</h2>
    </div>
  );
}

// ===================================
// CATEGORY COLORS
// ===================================

function getCategoryBadge(category) {
  switch (category) {
    case "Marketing":
      return "bg-pink-500/20 text-pink-400";

    case "Operations":
      return "bg-cyan-500/20 text-cyan-400";

    case "Salary":
      return "bg-green-500/20 text-green-400";

    case "Rent":
      return "bg-orange-500/20 text-orange-400";

    case "Fuel":
      return "bg-yellow-500/20 text-yellow-300";

    case "Utility":
      return "bg-indigo-500/20 text-indigo-400";

    case "Software":
      return "bg-purple-500/20 text-purple-400";

    case "Tax":
      return "bg-red-500/20 text-red-400";

    case "Travel":
      return "bg-sky-500/20 text-sky-400";

    case "Office":
      return "bg-gray-500/20 text-gray-300";

    default:
      return "bg-slate-500/20 text-slate-300";
  }
}

// ===================================
// PAYMENT COLORS
// ===================================

function getPaymentBadge(method) {
  switch (method) {
    case "Cash":
      return "bg-green-500/20 text-green-400";

    case "Bank Deposit":
      return "bg-blue-500/20 text-blue-400";

    case "Online Banking":
      return "bg-cyan-500/20 text-cyan-400";

    case "Debit Card":
      return "bg-purple-500/20 text-purple-400";

    case "Cheque":
      return "bg-indigo-500/20 text-indigo-400";

    case "EasyPaisa":
      return "bg-emerald-500/20 text-emerald-400";

    case "JazzCash":
      return "bg-red-500/20 text-red-400";

    case "NayaPay":
      return "bg-orange-500/20 text-orange-400";

    default:
      return "bg-slate-500/20 text-slate-300";
  }
}
