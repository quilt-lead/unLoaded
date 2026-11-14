import { lazy, Suspense, type ReactElement } from "react";
import { createBrowserRouter, RouterProvider, useRouteError, isRouteErrorResponse, Link, Navigate } from "react-router-dom";
import { AppShell } from "./AppShell";
import { Home } from "../routes/Home";
import { GlossaryPage } from "../help/GlossaryPage";

// Feature route folders are owned by their phase: src/routes/ifc + src/routes/set (R2), src/routes/v2 (R3).
// Each exports a default component with its own nested <Routes>, so adding pages never edits this file.
const IfcRoutes = lazy(() => import("../routes/ifc"));
const SetRoutes = lazy(() => import("../routes/set"));
const V2Routes = lazy(() => import("../routes/v2"));
const DevComponents = lazy(() => import("../routes/dev/ComponentsPage"));

const wait = (el: ReactElement) => <Suspense fallback={<div className="page muted">Loading...</div>}>{el}</Suspense>;

function RouteError() {
  const e = useRouteError();
  const msg = isRouteErrorResponse(e) ? `${e.status} ${e.statusText}` : e instanceof Error ? e.message : String(e);
  return (
    <div className="page" role="alert">
      <h1>Something went wrong</h1>
      <p className="page-lede">{msg}</p>
      <Link to="/">Back to the start</Link>
    </div>
  );
}

function NotFound() {
  return (
    <div className="page">
      <h1>Page not found</h1>
      <p className="page-lede">
        <Link to="/">Back to the start</Link>
      </p>
    </div>
  );
}

const router = createBrowserRouter([
  { path: "/review", element: <Navigate to="/ifc" replace /> },
  {
    element: <AppShell />,
    errorElement: <RouteError />,
    children: [
      { index: true, element: <Home /> },
      { path: "ifc/*", element: wait(<IfcRoutes />) },
      { path: "set/*", element: wait(<SetRoutes />) },
      { path: "v2/*", element: wait(<V2Routes />) },
      { path: "help", element: <GlossaryPage /> },
      { path: "dev/components", element: wait(<DevComponents />) },
      { path: "*", element: <NotFound /> },
    ],
  },
]);

export function App() {
  return <RouterProvider router={router} />;
}
