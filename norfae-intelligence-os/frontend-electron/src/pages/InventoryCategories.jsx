import { useNavigate } from "react-router-dom";

export default function InventoryCategories() {
  const navigate = useNavigate();

  return (
    <div className="p-8 text-white">
      <h1 className="text-5xl font-bold mb-3">Inventory</h1>

      <p className="text-slate-400 mb-10">Select a product category</p>

      <div className="grid grid-cols-3 gap-8">
        {/* Plush Toys */}

        <div
          onClick={() => navigate("/inventory/plush-toys")}
          className="
            cursor-pointer
            rounded-3xl
            bg-[#081028]
            border
            border-cyan-500/20
            p-8
            hover:border-cyan-400
            transition-all
          "
        >
          <h2 className="text-3xl font-bold">Plush Toys</h2>

          <p className="text-slate-400 mt-3">Plush Toys Inventory</p>
        </div>

        {/* Board Box */}

        <div
          onClick={() => navigate("/inventory/board-box")}
          className="
            cursor-pointer
            rounded-3xl
            bg-[#081028]
            border
            border-cyan-500/20
            p-8
            hover:border-cyan-400
            transition-all
          "
        >
          <h2 className="text-3xl font-bold">Board Box</h2>

          <p className="text-slate-400 mt-3">Board Games & Card Games</p>
        </div>

        {/* Future */}

        <div
          className="
            rounded-3xl
            border-2
            border-dashed
            border-slate-600
            p-8
          "
        >
          <h2 className="text-3xl font-bold">+ New Category</h2>

          <p className="text-slate-400 mt-3">Coming Soon</p>
        </div>
      </div>
    </div>
  );
}
