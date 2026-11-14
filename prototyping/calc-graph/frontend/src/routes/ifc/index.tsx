// R2 owns src/routes/ifc: the synthetic IFC app (model + calc package mapping, load path, impact).
import { Routes, Route } from "react-router-dom";
import IfcApp from "./IfcApp";

export default function IfcRoutes() {
  return (
    <Routes>
      <Route index element={<IfcApp />} />
    </Routes>
  );
}
