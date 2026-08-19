import { useEffect, useState } from "react";
import { accountApi, clearToken, getToken } from "./api";
import AuthPage from "./components/AuthPage";
import ResetPasswordPage from "./components/ResetPasswordPage";
import DashboardPage from "./pages/DashboardPage";
import DocVerificationPage from "./pages/DocVerificationPage";
import Sidebar from "./components/Sidebar";
import LogsPage from "./pages/LogsPage";
import MailsPage from "./pages/MailsPage";
import SettingsPage from "./pages/SettingsPage";
import UsersPage from "./pages/UsersPage";

const pages = new Set(["dashboard", "mails", "verification", "logs", "settings", "users", "reset-password"]);

// UPDATED: Check if the module key exists in the object instead of using .includes()
function hasModuleAccess(account, module) {
  return account?.role === "admin" || !!account?.module_access?.[module];
}

function canAccessView(account, view) {
  if (view === "mails") return hasModuleAccess(account, "background_verification");
  if (view === "verification") return hasModuleAccess(account, "document_verification");
  if (view === "users") return account?.role === "admin";
  return true;
}

function viewFromHash() {
  const hash = window.location.hash.replace("#/", "");
  const page = hash.split("?")[0];
  return pages.has(page) ? page : "dashboard";
}

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(Boolean(getToken()));
  const [activeView, setActiveView] = useState(viewFromHash);
  const [account, setAccount] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [refreshSignal, setRefreshSignal] = useState(0);
  const [darkMode, setDarkMode] = useState(
    localStorage.getItem("theme") !== "light",
  );

  function handleLogout() {
    clearToken();
    setIsAuthenticated(false);
    setAccount(null);
    window.location.hash = "#/dashboard";
  }

  function navigateTo(view) {
    window.location.hash = `#/${view}`;
  }

  useEffect(() => {
    document.documentElement.dataset.theme = darkMode ? "dark" : "light";
    localStorage.setItem("theme", darkMode ? "dark" : "light");
  }, [darkMode]);

  useEffect(() => {
    function syncViewFromHash() {
      setActiveView(viewFromHash());
    }

    if (!window.location.hash) {
      window.location.hash = "#/dashboard";
    }

    window.addEventListener("hashchange", syncViewFromHash);
    syncViewFromHash();
    return () => window.removeEventListener("hashchange", syncViewFromHash);
  }, []);

  useEffect(() => {
    if (!isAuthenticated) return;
    accountApi
      .me()
      .then(setAccount)
      .catch((err) => {
        setError(err.message);
        handleLogout();
      });
  }, [isAuthenticated]);

  useEffect(() => {
    if (!account || canAccessView(account, activeView)) return;
    navigateTo("dashboard");
  }, [account, activeView]);

  if (!isAuthenticated && activeView === "reset-password") {
    return <ResetPasswordPage />;
  }

  if (!isAuthenticated) {
    return <AuthPage onAuthenticated={() => setIsAuthenticated(true)} />;
  }

  return (
    <div className="appShell">
      <Sidebar
        account={account}
        activeView={activeView}
        onLogout={handleLogout}
        onNavigate={navigateTo}
      />
      <div className="contentShell">
        <main className="pageContent">
          {error && <div className="errorBanner">{error}</div>}

          {activeView === "dashboard" && (
            <DashboardPage
              account={account}
              onLogout={handleLogout}
              onNavigate={navigateTo}
              onError={setError}
            />
          )}

          {activeView === "mails" && canAccessView(account, "mails") && (
            <MailsPage
              account={account}
              onLogout={handleLogout}
              refreshSignal={refreshSignal}
              loading={loading}
              onRefresh={() => setRefreshSignal((current) => current + 1)}
              onLoadingChange={setLoading}
              onError={setError}
            />
          )}

          {activeView === "verification" && canAccessView(account, "verification") && (
            <DocVerificationPage 
              account={account} 
              onLogout={handleLogout} 
              onError={setError} 
            />
          )}

          {activeView === "logs" && (
            <LogsPage
              account={account}
              onLogout={handleLogout}
              refreshSignal={refreshSignal}
              onLoadingChange={setLoading}
              onError={setError}
            />
          )}

          {activeView === "settings" && (
            <SettingsPage
              account={account}
              onLogout={handleLogout}
              darkMode={darkMode}
              onDarkModeChange={setDarkMode}
            />
          )}

          {activeView === "users" && canAccessView(account, "users") && (
            <UsersPage account={account} onLogout={handleLogout} />
          )}
        </main>
      </div>
    </div>
  );
}