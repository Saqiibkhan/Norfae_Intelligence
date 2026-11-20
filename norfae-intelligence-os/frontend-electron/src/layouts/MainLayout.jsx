import { Link } from "react-router-dom";

export default function MainLayout({ children }) {
  return (
    <div className="flex h-screen bg-slate-950 text-white">
      <aside className="w-64 bg-slate-900 border-r border-slate-800 p-5">
        <h1 className="text-2xl font-bold mb-8">Norfae OS</h1>

        <nav className="flex flex-col gap-4">
          <Link to="/">Dashboard</Link>

          <Link to="/orders">Orders</Link>

          <Link to="/products">Products</Link>

          <Link to="/expenses">Expenses</Link>

          <Link to="/reports">Reports</Link>

          <Link to="/meta-ads">Meta Ads</Link>

          <Link to="/city-intelligence">City Intelligence</Link>

          <Link to="/settings">Settings</Link>
        </nav>
      </aside>

      <main className="flex-1 p-6 overflow-auto">{children}</main>
    </div>
  );
}
