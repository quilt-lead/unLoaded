import { NavLink, Outlet, Link } from "react-router-dom";
import { InfoTip } from "../help/InfoTip";
import { useTheme } from "../theme/ThemeProvider";
import "./shell.css";

/** The viewers the switch offers. */
const VIEWS = [
  { to: "/ifc", label: "IFC model", title: "Harbor View (synthetic v2): BIM model + calc package mapping (3D IFC viewer)" },
  { to: "/set", label: "Drawing set", title: "Harbor View (synthetic v2): drawing set and calc package read as documents; every node opens the original PDF" },
  { to: "/v2", label: "Move a column", title: "Synthetic v2: move or remove a column, see the impact" },
] as const;

export function AppShell() {
  const { resolved, toggle } = useTheme();
  return (
    <div className="shell">
      <header className="shell-head">
        <Link to="/" className="shell-brand">
          Calc Graph
        </Link>
        <nav className="viewswitch" aria-label="Switch viewer">
          {VIEWS.map((v) => (
            <NavLink key={v.to} to={v.to} title={v.title} className={({ isActive }) => (isActive ? "on" : undefined)}>
              {v.label}
            </NavLink>
          ))}
        </nav>
        <InfoTip id="nav.viewer-switch" />
        <span className="spacer" />
        <span className="shell-tool">
          <NavLink to="/help" className={({ isActive }) => `btn sm${isActive ? " on" : ""}`}>
            Glossary
          </NavLink>
          <InfoTip id="nav.help" />
        </span>
        <span className="shell-tool">
          <button
            type="button"
            className="btn sm"
            onClick={toggle}
            aria-label={`Switch to ${resolved === "dark" ? "light" : "dark"} theme`}
            title="Toggle theme"
          >
            {resolved === "dark" ? "Light" : "Dark"}
          </button>
          <InfoTip id="nav.theme" />
        </span>
      </header>
      <main className="shell-main">
        <Outlet />
      </main>
    </div>
  );
}
