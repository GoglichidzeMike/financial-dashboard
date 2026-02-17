import { NavLink } from "react-router-dom";

const NAV_ITEMS = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/transactions", label: "Transactions" },
];

export function TopNav() {
  return (
    <nav className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white p-1.5">
      {NAV_ITEMS.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          className={({ isActive }) =>
            `rounded-md px-3 py-2 text-sm font-semibold transition ${
              isActive
                ? "bg-cyan-50 text-cyan-700"
                : "text-slate-600 hover:bg-slate-50 hover:text-slate-800"
            }`
          }
        >
          {item.label}
        </NavLink>
      ))}
    </nav>
  );
}
