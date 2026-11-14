// R2 owns src/routes/set. Placeholder until the drawing-set view is ported.
import { Routes, Route } from "react-router-dom";

export default function SetRoutes() {
  return (
    <Routes>
      <Route
        index
        element={
          <div className="page">
            <h1>Drawing-set view</h1>
            <p className="page-lede">
              Being ported to React. Meanwhile use the <a href="/legacy/set.html">legacy page</a>.
            </p>
          </div>
        }
      />
    </Routes>
  );
}
