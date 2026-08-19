import { useState } from "react";
import { User, Lock } from "lucide-react";
import { apiRequest } from "../api";

export default function ResetPasswordPage() {
  const [isRequestMode, setIsRequestMode] = useState(true);
  const [form, setForm] = useState({ email: "", pin: "", new_password: "" });
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  function updateField(event) {
    setForm((current) => ({
      ...current,
      [event.target.name]: event.target.value,
    }));
  }

  async function handleRequest(event) {
    event.preventDefault();
    setError("");
    setMessage("");
    setSubmitting(true);

    try {
      const data = await apiRequest("/auth/password-reset-request", {
        method: "POST",
        body: JSON.stringify({ email: form.email }),
      });
      setMessage(data.message);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleReset(event) {
    event.preventDefault();
    setError("");
    setMessage("");
    setSubmitting(true);

    try {
      const data = await apiRequest("/auth/password-reset", {
        method: "POST",
        body: JSON.stringify({
          email: form.email,
          pin: form.pin,
          new_password: form.new_password,
        }),
      });
      setMessage(data.message);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="authPage">
      <section className="authPanel">
        <h1 className="authTitle">{isRequestMode ? "Reset Password" : "Enter New Password"}</h1>

        <div className="authToggleRow">
          <button
            className={`authToggleBtn ${isRequestMode ? "active" : ""}`}
            onClick={() => setIsRequestMode(true)}
            type="button"
          >
            Request Reset
          </button>
          <button
            className={`authToggleBtn ${!isRequestMode ? "active" : ""}`}
            onClick={() => setIsRequestMode(false)}
            type="button"
          >
            Confirm Reset
          </button>
        </div>

        <form className="authForm" onSubmit={isRequestMode ? handleRequest : handleReset}>
          {isRequestMode ? (
            <div className="inputGroup">
              <input
                name="email"
                onChange={updateField}
                required
                type="email"
                placeholder="Email"
                value={form.email}
              />
              <User className="inputIcon" size={18} />
            </div>
          ) : (
            <>
              <div className="inputGroup">
                <input
                  name="email"
                  onChange={updateField}
                  required
                  type="email"
                  placeholder="Email"
                  value={form.email}
                />
                <User className="inputIcon" size={18} />
              </div>
              <div className="inputGroup">
                <input
                  name="pin"
                  onChange={updateField}
                  required
                  type="text"
                  placeholder="Reset PIN"
                  value={form.pin}
                />
                <Lock className="inputIcon" size={18} />
              </div>
              <div className="inputGroup">
                <input
                  name="new_password"
                  onChange={updateField}
                  required
                  type="password"
                  placeholder="New Password"
                  value={form.new_password}
                />
                <Lock className="inputIcon" size={18} />
              </div>
            </>
          )}

          {error && <div className="errorBanner">{error}</div>}
          {message && <div className="successBanner">{message}</div>}

          <button className="authSubmitBtn" disabled={submitting} type="submit">
            {submitting ? "Please wait" : isRequestMode ? "Send Reset Email" : "Reset Password"}
          </button>

          <div className="authFormActionRow" style={{ marginTop: "10px", justifyContent: "center" }}>
            <a
              href="#/ "
              className="forgotPasswordLink"
              onClick={(e) => {
                e.preventDefault();
                window.location.hash = "#/";
              }}
            >
              Back to Login
            </a>
          </div>
        </form>
      </section>
    </main>
  );
}
