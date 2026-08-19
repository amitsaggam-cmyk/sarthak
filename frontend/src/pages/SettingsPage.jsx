import { Moon, Sun } from "lucide-react";
import ProfileDropdown from "../components/ProfileDropdown";

export default function SettingsPage({ account, onLogout, darkMode, onDarkModeChange }) {
  return (
    <section className="contentPage">
      <div className="pageTitleRow">
        <div>
          <p className="eyebrow">Preferences</p>
          <h1>Settings</h1>
        </div>
        <ProfileDropdown account={account} onLogout={onLogout} />
      </div>
      <div className="settingsGrid">
        <section className="panel settingsPanel">
          <div className="panelHeader">
            <h2>Appearance</h2>
          </div>
          <div className="settingRow">
            <span>Dark mode</span>
            <button
              aria-label="Toggle dark mode"
              aria-pressed={darkMode}
              className={darkMode ? "themeToggle on" : "themeToggle"}
              onClick={() => onDarkModeChange(!darkMode)}
              title="Toggle dark mode"
              type="button"
            >
              <span className="themeToggleThumb">
                {darkMode ? <Moon size={13} /> : <Sun size={13} />}
              </span>
            </button>
          </div>
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
