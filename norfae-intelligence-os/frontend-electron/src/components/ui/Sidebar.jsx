import { Link, useLocation } from "react-router-dom";

const links = [
  { name: "Dashboard", path: "/" },

  { name: "Orders", path: "/orders" },

  { name: "Expenses", path: "/expenses" },

  { name: "Meta Ads", path: "/meta-ads" },

  { name: "Reports", path: "/reports" },

  { name: "Product Intelligence", path: "/product-intelligence" },

  { name: "Cities Intelligence", path: "/city-intelligence" },

  { name: "Inventory", path: "/inventory" },

  { name: "Settings", path: "/settings" },
];

function Sidebar() {
  const location = useLocation();

  return (
    <aside
      className="
        w-[270px]
        min-h-screen
        bg-[#020817]
        border-r
        border-cyan-500/10
        px-5
        py-6
        flex
        flex-col
      "
    >
      {/* =================================== */}
      {/* LOGO */}
      {/* =================================== */}

      <div className="mb-12">
        <h1
          className="
            text-4xl
            font-black
            tracking-tight
            text-white
          "
        >
          Norfae
          <span className="text-cyan-400 ml-2">OS</span>
        </h1>

        <p
          className="
            text-slate-500
            text-sm
            mt-2
          "
        >
          Intelligence Operating System
        </p>
      </div>

      {/* =================================== */}
      {/* NAVIGATION */}
      {/* =================================== */}

      <nav className="flex flex-col gap-3">
        {links.map((link) => {
          const active =
            link.path === "/inventory"
              ? location.pathname.startsWith("/inventory")
              : location.pathname === link.path;

          return (
            <Link
              key={link.name}
              to={link.path}
              className={`
                relative
                px-5
                py-4
                rounded-2xl
                text-[17px]
                font-semibold
                transition-all
                duration-300
                border

                ${
                  active
                    ? `
                      bg-gradient-to-r
                      from-cyan-500/20
                      to-blue-500/20
                      border-cyan-400/20
                      text-white
                      shadow-[0_0_25px_rgba(34,211,238,0.08)]
                    `
                    : `
                      bg-transparent
                      border-transparent
                      text-slate-300
                      hover:bg-slate-900/70
                      hover:border-slate-800
                      hover:text-white
                    `
                }
              `}
            >
              {/* ACTIVE GLOW BAR */}

              {active && (
                <div
                  className="
                    absolute
                    left-0
                    top-3
                    bottom-3
                    w-1
                    rounded-full
                    bg-cyan-400
                  "
                />
              )}

              {link.name}
            </Link>
          );
        })}
      </nav>

      {/* =================================== */}
      {/* FOOTER */}
      {/* =================================== */}

      <div className="mt-auto pt-8">
        <div
          className="
            rounded-2xl
            border
            border-cyan-500/10
            bg-gradient-to-br
            from-cyan-500/5
            to-blue-500/5
            p-4
          "
        >
          <div
            className="
              text-cyan-300
              text-sm
              font-semibold
              mb-1
            "
          >
            Norfae Intelligence
          </div>

          <div
            className="
              text-slate-500
              text-xs
              leading-relaxed
            "
          >
            Business intelligence, operational tracking and scaling systems.
          </div>
        </div>
      </div>
    </aside>
  );
}

export default Sidebar;
