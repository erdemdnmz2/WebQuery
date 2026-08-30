import React, { Suspense, lazy } from 'react';
import { HashRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { SessionProvider, useSession } from './lib/session';
import { ThemeProvider } from './lib/theme';
import { WorkspacesProvider } from './lib/workspaces';
import { AppShell } from './components/app/AppShell';
import { ToastProvider } from './components/ui/Toast';
import { TooltipProvider } from './components/ui/Tooltip';
import { Skeleton } from './components/ui/Skeleton';
import Login from './pages/Login';
import NotFound from './pages/NotFound';
import Register from './pages/Register';
import Workspaces from './pages/Workspaces';

/*
 * The editor and the admin console pull in CodeMirror, which nobody needs on
 * the workspace list or the sign-in screen. They load when first routed to.
 */
const Studio = lazy(() => import('./pages/Studio'));
const RunWorkspace = lazy(() => import('./pages/RunWorkspace'));
const Admin = lazy(() => import('./pages/Admin'));

/** Placeholder that matches the shell so the first paint does not jump. */
const RouteFallback: React.FC = () => (
  <div className="flex flex-col gap-3 py-2">
    <Skeleton className="h-7 w-56" />
    <Skeleton className="h-4 w-80" />
    <Skeleton className="mt-3 h-72 w-full rounded-md" />
  </div>
);

const RequireAuth: React.FC<{ children: React.ReactNode; fullBleed?: boolean }> = ({ children, fullBleed }) => {
  const { status } = useSession();
  const location = useLocation();

  if (status === 'loading') return <RouteFallback />;
  if (status === 'anonymous') return <Navigate to="/login" replace state={{ from: location.pathname }} />;

  return (
    <AppShell fullBleed={fullBleed}>
      <Suspense fallback={<RouteFallback />}>{children}</Suspense>
    </AppShell>
  );
};

const RedirectIfAuthenticated: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { status } = useSession();
  if (status === 'loading') return <RouteFallback />;
  if (status === 'authenticated') return <Navigate to="/" replace />;
  return <>{children}</>;
};

const App: React.FC = () => (
  <ThemeProvider>
    <TooltipProvider>
      <ToastProvider>
        <HashRouter>
          <SessionProvider>
            <WorkspacesProvider>
              <Routes>
                <Route
                  path="/login"
                  element={
                    <RedirectIfAuthenticated>
                      <Login />
                    </RedirectIfAuthenticated>
                  }
                />
                <Route
                  path="/register"
                  element={
                    <RedirectIfAuthenticated>
                      <Register />
                    </RedirectIfAuthenticated>
                  }
                />
                <Route
                  path="/"
                  element={
                    <RequireAuth>
                      <Workspaces />
                    </RequireAuth>
                  }
                />
                <Route
                  path="/editor"
                  element={
                    <RequireAuth fullBleed>
                      <Studio />
                    </RequireAuth>
                  }
                />
                <Route
                  path="/editor/:workspaceId"
                  element={
                    <RequireAuth fullBleed>
                      <Studio />
                    </RequireAuth>
                  }
                />
                <Route
                  path="/execute/:workspaceId"
                  element={
                    <RequireAuth fullBleed>
                      <RunWorkspace />
                    </RequireAuth>
                  }
                />
                <Route
                  path="/admin"
                  element={
                    <RequireAuth>
                      <Admin />
                    </RequireAuth>
                  }
                />
                <Route
                  path="*"
                  element={
                    <RequireAuth>
                      <NotFound />
                    </RequireAuth>
                  }
                />
              </Routes>
            </WorkspacesProvider>
          </SessionProvider>
        </HashRouter>
      </ToastProvider>
    </TooltipProvider>
  </ThemeProvider>
);

export default App;
