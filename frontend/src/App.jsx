import { useEffect, useState } from "react";
import { accountApi, clearToken, getToken } from "./api";
import AuthPage from "./components/AuthPage";
import Sidebar from "./components/Sidebar";
import LogsView from "./views/LogsView";
import MailsView from "./views/MailsView";
import SettingsView from "./views/SettingsView";


const pages = new Set(["mails", "logs", "settings"]);


function viewFromHash() {
  const page = window.location.hash.replace("#/", "");
  return pages.has(page) ? page : "mails";
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
    window.location.hash = "#/mails";
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
      window.location.hash = "#/mails";
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
          {activeView === "mails" && (
            <MailsView
              refreshSignal={refreshSignal}
              loading={loading}
              onRefresh={() => setRefreshSignal((current) => current + 1)}
              onLoadingChange={setLoading}
              onError={setError}
            />
          )}
          {activeView === "logs" && (
            <LogsView
              refreshSignal={refreshSignal}
              onLoadingChange={setLoading}
              onError={setError}
            />
          )}
          {activeView === "settings" && (
            <SettingsView
              account={account}
              darkMode={darkMode}
              onDarkModeChange={setDarkMode}
            />
          )}
        </main>
      </div>
    </div>
  );
}



