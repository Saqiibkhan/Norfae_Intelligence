import { useState } from "react";
import axios from "axios";
import { toast } from "sonner";

const API_BASE = "http://127.0.0.1:8000";

export default function EditMatchModal({
  item,

  onClose,

  onUpdated,
}) {
  const [sku, setSku] = useState(item?.sku || "");

  const [quantity, setQuantity] = useState(item?.quantity || 1);

  const [size, setSize] = useState(item?.size || "");

  const [loading, setLoading] = useState(false);

  const handleSave = async () => {
    try {
      setLoading(true);

      console.log("UPDATING ITEM:", item);

      await axios.put(
        `${API_BASE}/order-items/${item.id}`,

        {
          sku,
          quantity,
          size,
        },
      );

      toast.success("Order item updated successfully");

      onUpdated();

      onClose();
    } catch (error) {
      console.error(error);

      toast.error("Failed to update order item");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="
        fixed
        inset-0
        bg-black/70
        flex
        items-center
        justify-center
        z-50
      "
    >
      <div
        className="
          bg-[#0B1120]
          border
          border-white/10
          rounded-2xl
          p-6
          w-[420px]
          shadow-2xl
        "
      >
        {/* ======================= */}
        {/* TITLE */}
        {/* ======================= */}

        <h2
          className="
            text-2xl
            font-bold
            text-white
            mb-6
          "
        >
          Edit Match
        </h2>

        {/* ======================= */}
        {/* SKU */}
        {/* ======================= */}

        <div className="mb-5">
          <label
            className="
              block
              text-sm
              text-slate-300
              mb-2
            "
          >
            SKU
          </label>

          <input
            type="text"
            value={sku}
            onChange={(e) => setSku(e.target.value)}
            className="
              w-full
              bg-[#111827]
              border
              border-white/10
              rounded-xl
              p-3
              text-white
              outline-none
            "
          />
        </div>

        {/* ======================= */}
        {/* QUANTITY */}
        {/* ======================= */}

        <div className="mb-5">
          <label
            className="
              block
              text-sm
              text-slate-300
              mb-2
            "
          >
            Quantity
          </label>

          <input
            type="number"
            value={quantity}
            onChange={(e) => setQuantity(Number(e.target.value))}
            className="
              w-full
              bg-[#111827]
              border
              border-white/10
              rounded-xl
              p-3
              text-white
              outline-none
            "
          />
        </div>

        {/* ======================= */}
        {/* SIZE */}
        {/* ======================= */}

        <div className="mb-6">
          <label
            className="
              block
              text-sm
              text-slate-300
              mb-2
            "
          >
            Size
          </label>

          <input
            type="text"
            value={size}
            onChange={(e) => setSize(e.target.value)}
            className="
              w-full
              bg-[#111827]
              border
              border-white/10
              rounded-xl
              p-3
              text-white
              outline-none
            "
          />
        </div>

        {/* ======================= */}
        {/* ACTIONS */}
        {/* ======================= */}

        <div
          className="
            flex
            justify-end
            gap-3
          "
        >
          <button
            onClick={onClose}
            className="
              px-5
              py-2
              rounded-xl
              border
              border-white/10
              text-white
              hover:bg-white/10
              transition
            "
          >
            Cancel
          </button>

          <button
            onClick={handleSave}
            disabled={loading}
            className="
              px-5
              py-2
              rounded-xl
              bg-blue-600
              hover:bg-blue-500
              text-white
              transition
            "
          >
            {loading ? "Saving..." : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}
