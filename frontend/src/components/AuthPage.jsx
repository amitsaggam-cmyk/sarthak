import { useState } from "react";
import { login, signup } from "../api";

const initialForm = {
  full_name: "",
  email: "",
  password: "",
};

export default function AuthPage({ onAuthenticated }) {
  const [isSignup, setIsSignup] = useState(false);
  const [form, setForm] = useState(initialForm);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
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
    setMessage("");
    setSubmitting(true);

    try {
      if (isSignup) {
        await signup(form);
        setMessage("Account created. Please login.");
        setIsSignup(false);
        setForm((current) => ({ ...current, password: "" }));
      } else {
        await login(form.email, form.password);
        onAuthenticated();
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="authPage">
      <section className="authPanel">
        <p className="eyebrow">HR background verification</p>
        <h1>{isSignup ? "Create account" : "Login"}</h1>
        <form className="authForm" onSubmit={handleSubmit}>
          {isSignup && (
            <label>
              Full name
              <input
                name="full_name"
                onChange={updateField}
                required
                type="text"
                value={form.full_name}
              />
            </label>
          )}
          <label>
            Email
            <input
              name="email"
              onChange={updateField}
              required
              type="email"
              value={form.email}
            />
          </label>
          <label>
            Password
            <input
              name="password"
              onChange={updateField}
              required
              type="password"
              value={form.password}
            />
          </label>
          {error && <div className="errorBanner">{error}</div>}
          {message && <div className="successBanner">{message}</div>}
          <button className="primaryAction authSubmit" disabled={submitting} type="submit">
            {submitting ? "Please wait" : isSignup ? "Sign up" : "Login"}
          </button>
        </form>
        <button
          className="linkButton"
          onClick={() => {
            setIsSignup((current) => !current);
            setError("");
            setMessage("");
          }}
          type="button"
        >
          {isSignup ? "Already have an account? Login" : "Need an account? Sign up"}
        </button>
      </section>
    </main>
  );
}
