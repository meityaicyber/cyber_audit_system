import React, { Suspense } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { ErrorBoundary } from 'react-error-boundary';
import { useAuth } from './contexts/AuthContext';
import { Box, CircularProgress } from '@mui/material';

import Layout from './components/Layout';
import ProtectedRoute from './components/ProtectedRoute';
import RoleGuard from './components/RoleGuard';
import BulkProgressWidget from './components/BulkProgressWidget';
import GlobalErrorBoundary from './components/GlobalErrorBoundary';

const LoginPage = React.lazy(() => import('./pages/LoginPage'));
const DashboardPage = React.lazy(() => import('./pages/DashboardPage'));
const UploadReportPage = React.lazy(() => import('./pages/UploadReportPage'));
const ReportsPage = React.lazy(() => import('./pages/ReportsPage'));
const ReportDetailPage = React.lazy(() => import('./pages/ReportDetailPage'));
const UserManagementPage = React.lazy(() => import('./pages/UserManagementPage'));
const AgencyManagementPage = React.lazy(() => import('./pages/AgencyManagementPage'));
const AuditLogsPage = React.lazy(() => import('./pages/AuditLogsPage'));
const ProfilePage = React.lazy(() => import('./pages/ProfilePage'));
const AnalyticsDashboardPage = React.lazy(() => import('./pages/AnalyticsDashboardPage'));
const MLAnalyticsDashboardPage = React.lazy(() => import('./pages/MLAnalyticsDashboardPage'));

const GlobalLoader = () => (
  <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', background: '#0A0E17' }}>
    <CircularProgress sx={{ color: '#00D4FF' }} size={48} />
  </Box>
);

function App() {
  const { loading } = useAuth();

  if (loading) {
    return <GlobalLoader />;
  }

  return (
    <>
      <div className="cyber-grid"></div>
      <ErrorBoundary FallbackComponent={GlobalErrorBoundary}>
        <Suspense fallback={<GlobalLoader />}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route element={<ProtectedRoute />}>
              <Route element={<Layout />}>
                <Route path="/" element={<Navigate to="/dashboard" replace />} />
                <Route path="/dashboard" element={<DashboardPage />} />
                <Route path="/upload" element={<UploadReportPage />} />
                <Route path="/reports" element={<ReportsPage />} />
                <Route path="/reports/:id" element={<ReportDetailPage />} />
                <Route path="/profile" element={<ProfilePage />} />
                <Route path="/analytics" element={<AnalyticsDashboardPage />} />
                <Route path="/ml-analytics" element={<MLAnalyticsDashboardPage />} />
                <Route
                  path="/users"
                  element={
                    <RoleGuard roles={['ADMIN']}>
                      <UserManagementPage />
                    </RoleGuard>
                  }
                />
                <Route
                  path="/agencies"
                  element={
                    <RoleGuard roles={['ADMIN']}>
                      <AgencyManagementPage />
                    </RoleGuard>
                  }
                />
                <Route
                  path="/audit-logs"
                  element={
                    <RoleGuard roles={['ADMIN']}>
                      <AuditLogsPage />
                    </RoleGuard>
                  }
                />
              </Route>
            </Route>
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </Suspense>
      </ErrorBoundary>
      <BulkProgressWidget />
    </>
  );
}

export default App;
