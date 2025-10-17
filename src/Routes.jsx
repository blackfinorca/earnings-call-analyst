import React from "react";
import { BrowserRouter, Routes as RouterRoutes, Route } from "react-router-dom";
import ScrollToTop from "components/ScrollToTop";
import ErrorBoundary from "components/ErrorBoundary";
import NotFound from "pages/NotFound";
import EarningsDashboard from './pages/earnings-dashboard';
import CompanyAnalysisSummary from './pages/company-analysis-summary';

const Routes = () => {
  return (
    <BrowserRouter>
      <ErrorBoundary>
      <ScrollToTop />
      <RouterRoutes>
        {/* Define your route here */}
        <Route path="/" element={<EarningsDashboard />} />
        <Route path="/earnings-dashboard" element={<EarningsDashboard />} />
        <Route path="/company-analysis-summary" element={<CompanyAnalysisSummary />} />
        <Route path="*" element={<NotFound />} />
      </RouterRoutes>
      </ErrorBoundary>
    </BrowserRouter>
  );
};

export default Routes;
