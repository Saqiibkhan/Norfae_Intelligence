import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import api from "../services/api";

import { toast } from "sonner";

export default function Products() {
  const { category } = useParams();

  const navigate = useNavigate();

  const selectedCategory =
    category === "plush-toys"
      ? "Plush Toys"
      : category === "board-box"
        ? "Board Box"
        : "";
  const [products, setProducts] = useState([]);

  const [loading, setLoading] = useState(true);

  const [syncing, setSyncing] = useState(false);

  const [creating, setCreating] = useState(false);

  const [deleting, setDeleting] = useState(false);

  const [showAddModal, setShowAddModal] = useState(false);

  const [showDeleteModal, setShowDeleteModal] = useState(false);

  const [productToDelete, setProductToDelete] = useState(null);

  const [newProduct, setNewProduct] = useState({
    name: "",

    sku: "",

    category: selectedCategory,

    size: "",

    website_size: "",

    weight_kg: 0.5,

    buying_price: 0,

    selling_price: 0,

    stock: 0,
  });

  // ===================================
  // FETCH PRODUCTS
  // ===================================

  const fetchProducts = useCallback(async () => {
    try {
      const response = await api.get("/products", {
        params: {
          category: selectedCategory,
        },
      });

      setProducts(response.data);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  }, [selectedCategory]);

  useEffect(() => {
    const loadProducts = async () => {
      await fetchProducts();
    };

    loadProducts();
  }, [fetchProducts]);

  // ===================================
  // REALTIME PRODUCT UPDATE
  // ===================================

  const updateProductField = async (
    productId,

    field,

    value,
  ) => {
    try {
      await api.put(
        `/products/${productId}`,

        {
          [field]: value,
        },
      );

      await fetchProducts();
    } catch (error) {
      console.error(error);
    }
  };

  // ===================================
  // SYNC INVENTORY
  // ===================================

  const syncInventory = async () => {
    try {
      setSyncing(true);

      const response = await api.post("/inventory/import");

      toast.success(response.data.message);

      await fetchProducts();
    } catch (error) {
      console.error(error);

      toast.error("Inventory sync failed");
    } finally {
      setSyncing(false);
    }
  };

  // ===================================
  // CREATE PRODUCT
  // ===================================

  const createProduct = async () => {
    try {
      setCreating(true);

      const productData = {
        ...newProduct,
        category: selectedCategory,
      };

      await api.post("/products/", productData);

      toast.success("Product created successfully");

      setShowAddModal(false);

      setNewProduct({
        name: "",
        sku: "",
        category: selectedCategory,
        size: "",
        website_size: "",
        weight_kg: 0.5,
        buying_price: 0,
        selling_price: 0,
        stock: 0,
      });

      await fetchProducts();
    } catch (error) {
      console.error(error);

      toast.error("Failed to create product");
    } finally {
      setCreating(false);
    }
  };

  // ===================================
  // DELETE PRODUCT
  // ===================================

  const deleteProduct = async (productId) => {
    try {
      await api.delete(`/products/${productId}`);
      toast.success("Product deleted successfully");

      await fetchProducts();
    } catch (error) {
      console.error(error);

      toast.error("Failed to delete product");
    }
  };

  // ===================================
  // LOADING
  // ===================================

  if (loading) {
    return <div className="p-10 text-white">Loading Products...</div>;
  }

  // ===================================
  // UI
  // ===================================

  return (
    <div className="p-8 min-h-screen bg-[#020817] text-white">
      {/* =================================== */}
      {/* PAGE TITLE */}
      {/* =================================== */}

      <div className="mb-10">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-5xl font-black">{selectedCategory}</h1>

            <p className="text-slate-400 text-lg mt-3">
              Inventory intelligence and operational management
            </p>
          </div>

          <button
            onClick={() => navigate("/inventory")}
            className="
        h-12
        px-6
        rounded-2xl
        bg-[#1E293B]
        hover:bg-[#334155]
        transition-all
        font-semibold
        text-white
        flex
        items-center
        gap-2
      "
          >
            ← Back
          </button>
        </div>

        <div
          className="
    flex
    items-center
    gap-5
    mt-10
    mb-8
  "
        >
          {/* ============================== */}
          {/* SYNC BUTTON */}
          {/* ============================== */}

          <button
            onClick={syncInventory}
            disabled={syncing}
            className="
      h-14
      px-7
      rounded-2xl
      bg-gradient-to-r
      from-blue-600
      to-blue-500
      hover:scale-[1.02]
      transition-all
      font-bold
      text-white
      shadow-[0_0_25px_rgba(59,130,246,0.35)]
      flex
      items-center
      justify-center
    "
          >
            {syncing ? "Syncing Inventory..." : "Sync Inventory XLSX"}
          </button>

          {/* ============================== */}
          {/* ADD PRODUCT BUTTON */}
          {/* ============================== */}

          <button
            onClick={() => {
              setShowAddModal(true);
            }}
            className="
      h-14
      px-7
      rounded-2xl
      bg-gradient-to-r
      from-pink-300
      to-rose-500
      hover:scale-[1.02]
      transition-all
      font-bold
      text-white
      shadow-[0_0_25px_rgba(16,185,129,0.35)]
      flex
      items-center
      justify-center
    "
          >
            + Add Product
          </button>
        </div>
      </div>

      {/* =================================== */}
      {/* TABLE */}
      {/* =================================== */}

      <div className="overflow-x-auto rounded-3xl border border-white/10">
        <table className="w-full">
          <thead className="bg-[#1E293B]">
            <tr>
              <th className="p-5 text-left">SKU</th>

              <th className="p-5 text-left">Product</th>

              <th className="p-5 text-left">Category</th>

              <th className="p-5 text-left">Size</th>

              <th className="p-5 text-left">Buying</th>

              <th className="p-5 text-left">Selling</th>

              <th className="p-5 text-left">Stock</th>

              <th className="p-5 text-left">Weight KG</th>

              <th className="p-5 text-left">Action</th>
            </tr>
          </thead>

          <tbody>
            {products.map((product) => (
              <tr
                key={product.id}
                className="
                  border-t
                  border-white/10
                  bg-[#081028]
                "
              >
                {/* SKU */}

                <td className="p-5">{product.sku}</td>

                {/* PRODUCT NAME */}

                <td className="p-5 font-semibold">{product.name}</td>

                {/* CATEGORY */}

                <td className="p-5">{product.category}</td>

                {/* SIZE */}

                <td className="p-5">
                  <input
                    type="text"
                    value={product.size || ""}
                    onChange={(e) => {
                      const updatedProducts = [...products];

                      const index = updatedProducts.findIndex(
                        (p) => p.id === product.id,
                      );

                      updatedProducts[index].size = e.target.value;

                      setProducts(updatedProducts);
                    }}
                    onBlur={(e) =>
                      updateProductField(
                        product.id,

                        "size",

                        e.target.value,
                      )
                    }
                    className="
                      w-28
                      p-3
                      rounded-xl
                      bg-[#1E293B]
                      border
                      border-white/10
                      outline-none
                    "
                  />
                </td>

                {/* BUYING PRICE */}

                <td className="p-5">
                  <input
                    type="number"
                    value={product.buying_price || 0}
                    onChange={(e) => {
                      const updatedProducts = [...products];

                      const index = updatedProducts.findIndex(
                        (p) => p.id === product.id,
                      );

                      updatedProducts[index].buying_price = e.target.value;

                      setProducts(updatedProducts);
                    }}
                    onBlur={(e) =>
                      updateProductField(
                        product.id,

                        "buying_price",

                        parseFloat(e.target.value),
                      )
                    }
                    className="
                      w-28
                      p-3
                      rounded-xl
                      bg-[#1E293B]
                      border
                      border-white/10
                      outline-none
                    "
                  />
                </td>

                {/* SELLING PRICE */}

                <td className="p-5">
                  <input
                    type="number"
                    value={product.selling_price || 0}
                    onChange={(e) => {
                      const updatedProducts = [...products];

                      const index = updatedProducts.findIndex(
                        (p) => p.id === product.id,
                      );

                      updatedProducts[index].selling_price = e.target.value;

                      setProducts(updatedProducts);
                    }}
                    onBlur={(e) =>
                      updateProductField(
                        product.id,

                        "selling_price",

                        parseFloat(e.target.value),
                      )
                    }
                    className="
                      w-28
                      p-3
                      rounded-xl
                      bg-[#1E293B]
                      border
                      border-white/10
                      outline-none
                    "
                  />
                </td>

                {/* STOCK */}

                <td className="p-5">
                  <input
                    type="number"
                    value={product.stock || 0}
                    onChange={(e) => {
                      const updatedProducts = [...products];

                      const index = updatedProducts.findIndex(
                        (p) => p.id === product.id,
                      );

                      updatedProducts[index].stock = e.target.value;

                      setProducts(updatedProducts);
                    }}
                    onBlur={(e) =>
                      updateProductField(
                        product.id,

                        "stock",

                        parseInt(e.target.value),
                      )
                    }
                    className="
                      w-24
                      p-3
                      rounded-xl
                      bg-[#1E293B]
                      border
                      border-white/10
                      outline-none
                    "
                  />
                </td>

                {/* WEIGHT */}

                <td className="p-5">
                  <input
                    type="number"
                    step="0.01"
                    value={product.weight_kg || 0}
                    onChange={(e) => {
                      const updatedProducts = [...products];

                      const index = updatedProducts.findIndex(
                        (p) => p.id === product.id,
                      );

                      updatedProducts[index].weight_kg = e.target.value;

                      setProducts(updatedProducts);
                    }}
                    onBlur={(e) =>
                      updateProductField(
                        product.id,

                        "weight_kg",

                        parseFloat(e.target.value),
                      )
                    }
                    className="
                      w-24
                      p-3
                      rounded-xl
                      bg-[#1E293B]
                      border
                      border-white/10
                      outline-none
                    "
                  />
                </td>
                <td className="p-5">
                  <button
                    onClick={() => {
                      setProductToDelete(product);

                      setShowDeleteModal(true);
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
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showAddModal && (
        <div
          className="
        fixed
        inset-0
        z-50
        bg-black/70
        backdrop-blur-md
        overflow-y-auto
        flex
        justify-center
        pt-12
        pb-12
        px-4
      "
        >
          <div
            className="
          relative
          w-full
          max-w-3xl
          rounded-[32px]
          border
          border-cyan-500/10
          bg-[#020817]
          shadow-[0_0_60px_rgba(0,255,255,0.08)]
          overflow-hidden
        "
          >
            {/* ============================== */}
            {/* TOP GLOW */}
            {/* ============================== */}

            <div
              className="
            absolute
            top-0
            left-0
            w-full
            h-32
            bg-cyan-500/5
            blur-3xl
          "
            />

            {/* ============================== */}
            {/* CONTENT */}
            {/* ============================== */}

            <div
              className="
              relative
              p-7
              max-h-[88vh]
              overflow-y-auto
            "
            >
              {/* ============================== */}
              {/* HEADER */}
              {/* ============================== */}

              <div className="mb-6">
                <div
                  className="
                inline-flex
                items-center
                px-4
                py-2
                rounded-2xl
                bg-cyan-500/10
                border
                border-cyan-500/20
                text-cyan-300
                text-xs
                font-bold
                tracking-wider
                mb-4
              "
                >
                  PRODUCT MANAGEMENT
                </div>

                <h2
                  className="
                text-4xl
                font-black
                text-white
                tracking-tight
                mb-2
              "
                >
                  Add Product
                </h2>

                <p
                  className="
                text-slate-400
                text-sm
              "
                >
                  Create inventory products for operations and intelligence.
                </p>
              </div>

              {/* ============================== */}
              {/* FORM */}
              {/* ============================== */}

              <div
                className="
              grid
              grid-cols-3
              gap-4
            "
              >
                {Object.keys(newProduct).map((key) => (
                  <div key={key} className="space-y-1">
                    <label
                      className="
                      text-xs
                      font-bold
                      uppercase
                      tracking-widest
                      text-slate-400
                    "
                    >
                      {key.replaceAll("_", " ")}
                    </label>

                    <input
                      type={
                        typeof newProduct[key] === "number" ? "number" : "text"
                      }
                      placeholder={key.replaceAll("_", " ")}
                      value={newProduct[key]}
                      onChange={(e) => {
                        setNewProduct({
                          ...newProduct,

                          [key]:
                            typeof newProduct[key] === "number"
                              ? Number(e.target.value)
                              : e.target.value,
                        });
                      }}
                      className="
                      w-full
                      h-11
                      px-4
                      rounded-2xl
                      bg-[#0F172A]
                      border
                      border-white/10
                      text-white
                      text-sm
                      outline-none
                      transition-all
                      focus:border-cyan-400/40
                      focus:bg-[#111C33]
                    "
                    />
                  </div>
                ))}
              </div>

              {/* ============================== */}
              {/* ACTIONS */}
              {/* ============================== */}

              <div
                className="
              flex
              justify-end
              gap-3
              mt-5
            "
              >
                <button
                  onClick={() => {
                    setShowAddModal(false);
                  }}
                  className="
                px-6
                py-3
                rounded-2xl
                border
                border-white/10
                bg-white/5
                hover:bg-white/10
                text-white
                text-sm
                font-semibold
                transition-all
              "
                >
                  Cancel
                </button>

                <button
                  onClick={createProduct}
                  disabled={creating}
                  className="
                px-6
                py-3
                rounded-2xl
                bg-gradient-to-r
                from-cyan-500
                to-blue-600
                hover:scale-[1.02]
                transition-all
                text-white
                text-sm
                font-bold
                shadow-[0_0_30px_rgba(0,255,255,0.2)]
              "
                >
                  {creating ? "Creating..." : "Create Product"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {showDeleteModal && (
        <div
          className="
            fixed
            inset-0
            z-50
            bg-black/70
            backdrop-blur-sm
            flex
            items-center
            justify-center
        "
        >
          <div
            className="
                w-[480px]
                rounded-3xl
                bg-[#081028]
                border
                border-red-500/20
                p-8
            "
          >
            <h2 className="text-3xl font-bold text-white mb-3">
              Delete Product?
            </h2>

            <p className="text-slate-400 mb-8">This action cannot be undone.</p>

            <div className="flex justify-end gap-3">
              <button
                onClick={() => {
                  setShowDeleteModal(false);
                  setProductToDelete(null);
                }}
                className="
                        px-6
                        py-3
                        rounded-2xl
                        border
                        border-white/10
                        bg-white/5
                    "
              >
                Cancel
              </button>

              <button
                disabled={deleting}
                onClick={async () => {
                  setDeleting(true);

                  await deleteProduct(productToDelete.id);

                  setDeleting(false);

                  setShowDeleteModal(false);

                  setProductToDelete(null);
                }}
                className="
                        px-6
                        py-3
                        rounded-2xl
                        bg-red-600
                        text-white
                    "
              >
                {deleting ? "Deleting..." : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
