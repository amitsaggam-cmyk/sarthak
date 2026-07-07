const API_BASE_URL = "http://127.0.0.1:8000/api";
export { API_BASE_URL };

export function getToken() {
  return localStorage.getItem("access_token");
}

export function setToken(token) {
  localStorage.setItem("access_token", token);
}

export function clearToken() {
  localStorage.removeItem("access_token");
}

export async function apiRequest(path, options = {}) {
  const token = getToken();

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token && { Authorization: `Bearer ${token}` }),
      ...(options.headers || {}),
    },
  });

  const contentType = response.headers.get("content-type") || "";

  if (!contentType.includes("application/json")) {
    throw new Error("Backend API did not return JSON.");
  }

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.detail || "Request failed");
  }

  return data;
}

export async function login(email, password) {
  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: new URLSearchParams({
      username: email,
      password,
    }),
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.detail || "Login failed");
  }

  setToken(data.access_token);
  return data;
}

export async function signup(form) {
  return apiRequest("/auth/signup", {
    method: "POST",
    body: JSON.stringify(form),
    headers: {},
  });
}

export const emailsApi = {
  list: () => apiRequest("/emails"),
  verification: (emailId) => apiRequest(`/emails/${emailId}/verification`),
  decide: (emailId, decision) =>
    apiRequest(`/emails/${emailId}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision }),
    }),
};

export const logsApi = {
  list: () => apiRequest("/logs"),
};

export const accountApi = {
  me: () => apiRequest("/auth/me"),
};

export async function downloadAttachment(attachment) {
  const response = await fetch(`${API_BASE_URL}/attachments/${attachment.id}/download`, {
    headers: {
      Authorization: `Bearer ${getToken()}`,
    },
  });

  if (!response.ok) {
    throw new Error("Attachment download failed");
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = attachment.filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
