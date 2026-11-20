import { useState } from "react";
import axios from "axios";
import { toast } from "sonner";

const API_BASE = "http://127.0.0.1:8000";

export default function EditCityModal({ order, onClose, onUpdated }) {
  const [city, setCity] = useState(order?.city || "");

  const [province, setProvince] = useState(order?.province || "");

  const [loading, setLoading] = useState(false);

  const handleSave = async () => {
    try {
      setLoading(true);

      await axios.put(`${API_BASE}/orders/${order.id}/location`, {
        city,
        province,
      });

      toast.success("City updated successfully");

      onUpdated();

      onClose();
    } catch (error) {
      console.error(error);

      toast.error("Failed to update city");
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
        <h2
          className="
            text-2xl
            font-bold
            text-white
            mb-6
          "
        >
          Edit City
        </h2>

        {/* CITY */}

        <div className="mb-5">
          <label
            className="
              block
              text-sm
              text-slate-300
              mb-2
            "
          >
            City
          </label>

          <input
            type="text"
            value={city}
            onChange={(e) => setCity(e.target.value)}
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

        {/* PROVINCE */}

        <div className="mb-6">
          <label
            className="
              block
              text-sm
              text-slate-300
              mb-2
            "
          >
            Province
          </label>

          <select
            value={province}
            onChange={(e) => setProvince(e.target.value)}
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
          >
            <option value="">Auto Detect</option>

            <option value="Punjab">Punjab</option>

            <option value="Sindh">Sindh</option>

            <option value="KPK">KPK</option>

            <option value="Balochistan">Balochistan</option>

            <option value="AJK">AJK</option>

            <option value="Islamabad Capital Territory">
              Islamabad Capital Territory
            </option>

            <option value="Gilgit Baltistan">Gilgit Baltistan</option>
          </select>
        </div>

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
              bg-green-600
              hover:bg-green-500
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
