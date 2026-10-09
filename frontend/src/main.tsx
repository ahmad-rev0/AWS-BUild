import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { PlannerDashboard } from "./pages/PlannerDashboard";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <PlannerDashboard />
  </StrictMode>,
);
