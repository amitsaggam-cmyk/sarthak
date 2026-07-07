import { Moon, Sun } from "lucide-react";

export default function SettingsView({ account, darkMode, onDarkModeChange }) {
  return (
    <section className="contentPage">
      <div className="pageTitleRow">
        <div>
          <p className="eyebrow">Preferences</p>
          <h1>Settings</h1>
        </div>
      </div>
      <div className="settingsGrid">
        <section className="panel">
          <button
            aria-pressed={darkMode}
            className={darkMode ? "darkModeTile on" : "darkModeTile"}
            onClick={() => onDarkModeChange(!darkMode)}
            type="button"
          >
            <span>Dark mode</span>
            {darkMode ? <Moon size={18} /> : <Sun size={18} />}
          </button>
        </section>

        <section className="panel">
          <div className="panelHeader">
            <h2>Account</h2>
          </div>
          <dl className="accountDetails">
            <div>
              <dt>Name</dt>
              <dd>{account?.full_name || "HR User"}</dd>
            </div>
            <div>
              <dt>Email</dt>
              <dd>{account?.email || "Not available"}</dd>
            </div>
          </dl>
        </section>
      </div>
    </section>
  );
}
