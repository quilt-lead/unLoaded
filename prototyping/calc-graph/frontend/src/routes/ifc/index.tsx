// R2 owns src/routes/ifc. Placeholder until the synthetic IFC app is ported.
import { Routes, Route } from "react-router-dom";

export default function IfcRoutes() {
  return (
    <Routes>
      <Route
        index
        element={
          <div className="page">
            <h1>Synthetic IFC app</h1>
            <p className="page-lede">
              Being ported to React. Meanwhile use the <a href="/legacy/">legacy page</a>.
            </p>
          </div>
        }
      />
    </Routes>
  );
}
