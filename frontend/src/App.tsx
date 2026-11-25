import React, { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useAppStore } from './store/useAppStore';

import { MainLayout } from './components/layout/MainLayout';
import { LoginPage } from './pages/LoginPage';
import { OverviewDashboard } from './pages/OverviewDashboard';
import { TopologyPage } from './pages/TopologyPage';
import { DevicesPage } from './pages/DevicesPage';
import { InterfacesPage } from './pages/InterfacesPage';
import { VlanPage } from './pages/VlanPage';
import { RoutingPage } from './pages/RoutingPage';
import { MonitoringPage } from './pages/MonitoringPage';
import { IncidentsPage } from './pages/IncidentsPage';
import { RcaPage } from './pages/RcaPage';
import { DigitalTwinPage } from './pages/DigitalTwinPage';
import { RemediationPage } from './pages/RemediationPage';
import { TrainingLabPage } from './pages/TrainingLabPage';
import { AnalyticsPage } from './pages/AnalyticsPage';
import { AuditLogsPage } from './pages/AuditLogsPage';
import { SettingsPage } from './pages/SettingsPage';
import { CampusInventoryPage } from './pages/CampusInventoryPage';
import { FaultSimulationPage } from './pages/FaultSimulationPage';
import { ServicesSlaPage } from './pages/ServicesSlaPage';
import { SecurityOperationsPage } from './pages/SecurityOperationsPage';
import { NetworkIntegrationPage } from './pages/NetworkIntegrationPage';

export const App: React.FC = () => {
  const { setWsConnected } = useAppStore();

  useEffect(() => {
    // Connect WebSocket for live updates
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    let ws: WebSocket | null = null;

    try {
      ws = new WebSocket(wsUrl);
      ws.onopen = () => setWsConnected(true);
      ws.onclose = () => setWsConnected(false);
      ws.onerror = () => setWsConnected(false);
    } catch {
      setWsConnected(false);
    }

    return () => {
      if (ws) ws.close();
    };
  }, [setWsConnected]);

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        
        <Route path="/" element={<MainLayout />}>
          <Route index element={<OverviewDashboard />} />
          <Route path="topology" element={<TopologyPage />} />
          <Route path="campus-inventory" element={<CampusInventoryPage />} />
          <Route path="devices" element={<DevicesPage />} />
          <Route path="interfaces" element={<InterfacesPage />} />
          <Route path="vlans" element={<VlanPage />} />
          <Route path="routing" element={<RoutingPage />} />
          <Route path="monitoring" element={<MonitoringPage />} />
          <Route path="fault-simulation" element={<FaultSimulationPage />} />
          <Route path="incidents" element={<IncidentsPage />} />
          <Route path="services" element={<ServicesSlaPage />} />
          <Route path="security" element={<SecurityOperationsPage />} />
          <Route path="integrations" element={<NetworkIntegrationPage />} />
          <Route path="diagnostics" element={<RcaPage />} />
          <Route path="simulator" element={<DigitalTwinPage />} />
          <Route path="remediation" element={<RemediationPage />} />
          <Route path="training" element={<TrainingLabPage />} />
          <Route path="analytics" element={<AnalyticsPage />} />
          <Route path="audit" element={<AuditLogsPage />} />
          <Route path="settings" element={<SettingsPage />} />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
};
