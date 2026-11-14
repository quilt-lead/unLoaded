// R3 owns src/routes/v2. Placeholder until the move-a-column UI is built.
import { Routes, Route } from "react-router-dom";

export default function V2Routes() {
  return (
    <Routes>
      <Route
        index
        element={
          <div className="page">
            <h1>Move a column</h1>
            <p className="page-lede">The move-a-column, health meter and change-order UI is being built here (API: /api/v2).</p>
          </div>
        }
      />
    </Routes>
  );
}
