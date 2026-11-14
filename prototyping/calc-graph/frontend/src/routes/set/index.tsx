// R2 owns src/routes/set: the drawing-set view (elements, calc records, calc pages, connections,
// findings, graph, 3D from the plans, inspector and split evidence).
import { Routes, Route } from "react-router-dom";
import SetApp from "./SetApp";

export default function SetRoutes() {
  return (
    <Routes>
      <Route index element={<SetApp />} />
    </Routes>
  );
}
