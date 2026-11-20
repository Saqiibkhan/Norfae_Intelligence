import { BrowserRouter, Routes, Route } from "react-router-dom";

import Sidebar from "./components/ui/Sidebar";

import Dashboard from "./pages/Dashboard";
import Orders from "./pages/Orders";
import Products from "./pages/Products";
import Expenses from "./pages/Expenses";
import Reports from "./pages/Reports";
import MetaAds from "./pages/MetaAds";
import CityIntelligence from "./pages/CityIntelligence";
import Settings from "./pages/Settings";
import InventoryCategories from "./pages/InventoryCategories";
import ProductIntelligence from "./pages/ProductIntelligence";

function App() {
  return (
    <BrowserRouter>
      <div className="flex bg-slate-950 text-white min-h-screen">
        <Sidebar />

        <main className="flex-1 p-12 overflow-auto">
          <Routes>
            <Route path="/" element={<Dashboard />} />

            <Route path="/orders" element={<Orders />} />

            <Route path="/inventory" element={<InventoryCategories />} />

            <Route path="/inventory/:category" element={<Products />} />

            <Route path="/expenses" element={<Expenses />} />

            <Route path="/reports" element={<Reports />} />

            <Route path="/meta-ads" element={<MetaAds />} />

            <Route path="/city-intelligence" element={<CityIntelligence />} />

            <Route path="/settings" element={<Settings />} />

            <Route
              path="/product-intelligence"
              element={<ProductIntelligence />}
            />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;
