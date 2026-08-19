const API_BASE_URL = "http://127.0.0.1:8000/api";
export { API_BASE_URL };

export function getToken() {
  return localStorage.getItem("access_token");
}

export function getRefreshToken() {
  return localStorage.getItem("refresh_token");
}

export function setToken(token, refreshToken = null) {
  localStorage.setItem("access_token", token);
  if (refreshToken) {
    localStorage.setItem("refresh_token", refreshToken);
  }
}

export function clearToken() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
}

let refreshRequest = null;

async function refreshAccessToken() {
  const refreshToken = getRefreshToken();

  if (!refreshToken) {
    clearToken();
    return null;
  }

  if (!refreshRequest) {
    refreshRequest = fetch(`${API_BASE_URL}/auth/refresh`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })
      .then(async (response) => {
        const data = await response.json().catch(() => ({}));

        if (!response.ok) {
          clearToken();
          throw new Error(data.detail || "Session expired");
        }

        setToken(data.access_token, data.refresh_token);
        return data.access_token;
      })
      .finally(() => {
        refreshRequest = null;
      });
  }

  return refreshRequest;
}

async function authedFetch(url, options = {}, retryOnUnauthorized = true) {
  const token = getToken();
  const headers = {
    ...(token && { Authorization: `Bearer ${token}` }),
    ...(options.headers || {}),
  };

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (response.status !== 401 || !retryOnUnauthorized) {
    if (response.status === 401) {
      clearToken();
    }
    return response;
  }

  const refreshedToken = await refreshAccessToken();

  if (!refreshedToken) {
    clearToken();
    return response;
  }

  const retryResponse = await fetch(url, {
    ...options,
    headers: {
      ...headers,
      Authorization: `Bearer ${refreshedToken}`,
    },
  });

  if (retryResponse.status === 401) {
    clearToken();
  }

  return retryResponse;
}

export async function apiRequest(path, options = {}) {
  const response = await authedFetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });

  const contentType = response.headers.get("content-type") || "";

  if (!contentType.includes("application/json")) {
    throw new Error("Backend API did not return JSON.");
  }

  const data = await response.json();

  if (!response.ok) {
    if (response.status === 401) {
      clearToken();
    }
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

  setToken(data.access_token, data.refresh_token);
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
  decide: (emailId, decision, replyBody, note = "") =>
    apiRequest(`/emails/${emailId}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision, note, reply_body: replyBody }),
    }),
};

export const logsApi = {
  list: () => apiRequest("/logs"),
};

export const accountApi = {
  me: () => apiRequest("/auth/me"),
};

export const docVerificationApi = {
  list: () => apiRequest("/doc-verification/submissions"),
  detail: (submissionId) => apiRequest(`/doc-verification/submissions/${submissionId}`),
  confirmManualChanges: (submissionId, changes, expectedRevision) =>
    apiRequest(`/doc-verification/submissions/${submissionId}/manual-changes`, {
      method: "PATCH",
      body: JSON.stringify({ changes, expected_revision: expectedRevision }),
    }),
  replace: async (submissionId, targetFilename, file, expectedRevision) => {
    const formData = new FormData();
    formData.append("target_filename", targetFilename);
    formData.append("file", file);
    formData.append("expected_revision", String(expectedRevision));
    const response = await authedFetch(`${API_BASE_URL}/doc-verification/submissions/${submissionId}/replace`, {
      method: "POST",
      body: formData,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || "Could not replace document.");
    return data;
  },
  reanalyse: async (submissionId, expectedRevision) => {
    const formData = new FormData();
    formData.append("expected_revision", String(expectedRevision));
    const response = await authedFetch(`${API_BASE_URL}/doc-verification/submissions/${submissionId}/reanalyse`, {
      method: "POST",
      body: formData,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || "Could not start document reanalysis.");
    return data;
  },
  candidateSummary: (submissionId) =>
    apiRequest(`/doc-verification/submissions/${submissionId}/candidate-summary`),
  submit: async (files) => {
    const formData = new FormData();
    files.forEach((file) => formData.append("files", file));

    const response = await authedFetch(`${API_BASE_URL}/doc-verification/submit`, {
      method: "POST",
      body: formData,
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "Submission failed");
    }
    return data;
  },
  submitDrive: (driveUrl) =>
    apiRequest("/doc-verification/drive-submit", {
      method: "POST",
      body: JSON.stringify({ drive_url: driveUrl }),
    }),
  fileUrl: (submissionId, filename) =>
    `/doc-verification/submissions/${submissionId}/files/${encodeURIComponent(filename)}`,
};

export async function fetchAuthedFile(relativePath) {
  const response = await authedFetch(`${API_BASE_URL}${relativePath}`);
  if (!response.ok) {
    throw new Error("File fetch failed");
  }
  const blob = await response.blob();
  return { url: URL.createObjectURL(blob), contentType: blob.type };
}

export const usersApi = {
  list: () => apiRequest("/auth/users"),
  create: (form) =>
    apiRequest("/auth/users", {
      method: "POST",
      body: JSON.stringify(form),
    }),
  update: (userId, changes) =>
    apiRequest(`/auth/users/${userId}`, {
      method: "PATCH",
      body: JSON.stringify(changes),
    }),
  remove: (userId) =>
    apiRequest(`/auth/users/${userId}`, {
      method: "DELETE",
    }),
};

export async function downloadAttachment(attachment) {
  const response = await authedFetch(`${API_BASE_URL}/attachments/${attachment.id}/download`);

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

export async function getAttachmentPreview(attachment) {
  const response = await authedFetch(`${API_BASE_URL}/attachments/${attachment.id}/download`);

  if (!response.ok) {
    throw new Error("Attachment preview failed");
  }

  const blob = await response.blob();
  return {
    url: URL.createObjectURL(blob),
    contentType: blob.type || attachment.content_type || "application/octet-stream",
  };
}
