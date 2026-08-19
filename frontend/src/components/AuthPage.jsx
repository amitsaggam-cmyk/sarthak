import { useState } from "react";
import { User, Lock } from "lucide-react";
import { login } from "../api";

export default function AuthPage({ onAuthenticated }) {
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  function updateField(event) {
    setForm((current) => ({
      ...current,
      [event.target.name]: event.target.value,
    }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setSubmitting(true);

    try {
      await login(form.email, form.password);
      onAuthenticated();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="authPage">
      <section className="authPanel">
        <h1 className="authTitle">Login</h1>
        <form className="authForm" onSubmit={handleSubmit}>
          <div className="inputGroup">
            <input
              name="email"
              onChange={updateField}
              required
              type="email"
              placeholder="Username"
              value={form.email}
            />
            <User className="inputIcon" size={18} />
          </div>
          
          <div className="inputGroup">
            <input
              name="password"
              onChange={updateField}
              required
              type="password"
              placeholder="Password"
              value={form.password}
            />
            <Lock className="inputIcon" size={18} />
          </div>

          <div className="authFormActionRow">
            <a
              className="forgotPasswordLink"
              href="#/reset-password"
            >
              Forgot password?
            </a>
          </div>

          {error && <div className="errorBanner">{error}</div>}

          <button className="authSubmitBtn" disabled={submitting} type="submit">
            {submitting ? "Please wait" : "Login"}
          </button>
        </form>
      </section>
    </main>
  );
}
