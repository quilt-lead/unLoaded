// R3 owns src/routes/v2: the move-a-column UI on the synthetic v2 data (/api/v2).
import { lazy, Suspense, type ReactElement } from "react";
import { Routes, Route } from "react-router-dom";
import MovePage from "./MovePage";
import "./v2.css";

const ElementPage = lazy(() => import("./ElementPage"));
const EtabsPage = lazy(() => import("./EtabsPage"));
const InboxPage = lazy(() => import("./InboxPage"));

const wait = (el: ReactElement) => <Suspense fallback={<div className="page muted">Loading...</div>}>{el}</Suspense>;

export default function V2Routes() {
  return (
    <Routes>
      <Route index element={<MovePage />} />
      <Route path="element/:eid" element={wait(<ElementPage />)} />
      <Route path="etabs" element={wait(<EtabsPage />)} />
      <Route path="inbox" element={wait(<InboxPage />)} />
    </Routes>
  );
}
