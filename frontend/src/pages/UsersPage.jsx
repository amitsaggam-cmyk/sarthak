import { useEffect, useState } from "react";
import {
  Edit3,
  Eye,
  EyeOff,
  ShieldCheck,
  Trash2,
  UserPlus,
  UserRound,
  Users as UsersIcon,
  ChevronLeft,
  ChevronRight,
  Filter,
  Search,
  XCircle,
} from "lucide-react";
import { usersApi } from "../api";
import ProfileDropdown from "../components/ProfileDropdown";

const MODULE_OPTIONS = [
  { value: "background_verification", label: "Background Verification" },
  { value: "document_verification", label: "Document Verification" },
];

const initialForm = {
  full_name: "",
  email: "",
  password: "",
  role: "user",
  module_access: {},
};

const initialEditForm = {
  role: "user",
  is_active: true,
  module_access: {},
};

function normalizeModuleAccess(role, moduleAccess = {}) {
  if (role === "admin") {
    const adminAccess = {};
    MODULE_OPTIONS.forEach((module) => (adminAccess[module.value] = "write"));
    return adminAccess;
  }
  const validAccess = {};
  Object.entries(moduleAccess || {}).forEach(([key, val]) => {
    if (MODULE_OPTIONS.some((o) => o.value === key) && (val === "read" || val === "write")) {
      validAccess[key] = val;
    }
  });
  return validAccess;
}

function moduleAccessLabel(value) {
  return MODULE_OPTIONS.find((module) => module.value === value)?.label || value;
}

function ModuleAccessSelect({ disabled = false, value, onChange }) {
  if (disabled) {
    return (
      <div className="moduleAccessDropdown disabled">
        <div className="moduleAccessSummary" style={{ padding: "10px 12px" }}>All modules (Admin - Write)</div>
      </div>
    );
  }

  function handleAccessChange(module, level) {
    const next = { ...value };
    if (level === "none") {
      delete next[module];
    } else {
      next[module] = level;
    }
    onChange(next);
  }

  return (
    <div style={{ display: "grid", gap: "10px", background: "var(--bg-muted)", padding: "12px", borderRadius: "8px", border: "1px solid var(--border)" }}>
      {MODULE_OPTIONS.map((module) => (
        <div key={module.value} style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontSize: "13px", fontWeight: "600", color: "var(--text-main)" }}>{module.label}</span>
          <select
            style={{ minHeight: "32px", padding: "4px 8px", width: "140px", borderRadius: "6px", background: "var(--bg-card)", color: "var(--text-main)", border: "1px solid var(--border)" }}
            value={value[module.value] || "none"}
            onChange={(e) => handleAccessChange(module.value, e.target.value)}
          >
            <option value="none">No Access</option>
            <option value="read">Read Only</option>
            <option value="write">Read & Write</option>
          </select>
        </div>
      ))}
    </div>
  );
}

function ModuleAccessBadges({ user }) {
  const modules = normalizeModuleAccess(user.role, user.module_access);
  const entries = Object.entries(modules);
  
  if (!entries.length) {
    return <span className="badge badgeMismatch">None</span>;
  }
  
  return (
    <div className="moduleAccessBadges">
      {entries.map(([module, level]) => (
        <span className={level === "write" ? "badge badgeMatch" : "badge badgeToggle"} key={module}>
          {moduleAccessLabel(module)} ({level === "write" ? "Write" : "Read"})
        </span>
      ))}
    </div>
  );
}

export default function UsersPage({ account, onLogout }) {
  const [users, setUsers] = useState([]);
  const [form, setForm] = useState(initialForm);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [rowActionId, setRowActionId] = useState(null);
  const [page, setPage] = useState(1);
  const itemsPerPage = 5;

  const [showForm, setShowForm] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [editForm, setEditForm] = useState(initialEditForm);

  const [searchText, setSearchText] = useState("");
  const [showFilters, setShowFilters] = useState(false);
  const [roleFilter, setRoleFilter] = useState("all");
  const [moduleFilter, setModuleFilter] = useState("all");

  const adminCount = users.filter((user) => user.role === "admin").length;

  function updateField(event) {
    const nextValue = event.target.value;
    setForm((current) => ({
      ...current,
      [event.target.name]: nextValue,
      ...(event.target.name === "role" && {
        module_access: normalizeModuleAccess(nextValue, current.module_access),
      }),
    }));
  }

  async function loadUsers() {
    setLoading(true);
    setError("");
    try {
      setUsers(await usersApi.list());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setMessage("");
    setSubmitting(true);
    try {
      await usersApi.create({
        ...form,
        module_access: normalizeModuleAccess(form.role, form.module_access),
      });
      setMessage(`User "${form.full_name}" created successfully.`);
      setForm(initialForm);
      setShowForm(false);
      await loadUsers();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  function openEditUser(user) {
    setEditingUser(user);
    setEditForm({
      role: user.role,
      is_active: user.is_active,
      module_access: normalizeModuleAccess(user.role, user.module_access),
    });
    setError("");
    setMessage("");
  }

  async function handleEditSubmit(event) {
    event.preventDefault();
    if (!editingUser) return;

    setRowActionId(editingUser.id);
    setError("");
    setMessage("");

    try {
      await usersApi.update(editingUser.id, {
        ...editForm,
        module_access: normalizeModuleAccess(editForm.role, editForm.module_access),
      });
      setMessage(`User "${editingUser.full_name}" updated successfully.`);
      setEditingUser(null);
      await loadUsers();
    } catch (err) {
      setError(err.message);
    } finally {
      setRowActionId(null);
    }
  }

  async function handleDelete(user) {
    const confirmed = window.confirm(`Delete user "${user.full_name}"? This cannot be undone.`);
    if (!confirmed) return;

    setRowActionId(user.id);
    setError("");

    try {
      await usersApi.remove(user.id);
      await loadUsers();
    } catch (err) {
      setError(err.message);
    } finally {
      setRowActionId(null);
    }
  }

  useEffect(() => {
    loadUsers();
  }, []);

  useEffect(() => {
    setPage(1);
  }, [users, searchText, roleFilter, moduleFilter]);

  const filteredUsers = users.filter((user) => {
    const query = searchText.trim().toLowerCase();
    const modules = normalizeModuleAccess(user.role, user.module_access);

    const matchesSearch =
      !query ||
      user.full_name.toLowerCase().includes(query) ||
      user.email.toLowerCase().includes(query);

    const matchesRole = roleFilter === "all" || user.role === roleFilter;

    // A user matches the module filter if the module exists as a key in the object
    const matchesModule =
      moduleFilter === "all" ||
      (moduleFilter === "none" ? Object.keys(modules).length === 0 : !!modules[moduleFilter]);

    return matchesSearch && matchesRole && matchesModule;
  });

  const activeFilterCount = [roleFilter !== "all", moduleFilter !== "all"].filter(Boolean).length;

  const totalPages = Math.ceil(filteredUsers.length / itemsPerPage) || 1;
  const startIndex = (page - 1) * itemsPerPage;
  const endIndex = Math.min(startIndex + itemsPerPage, filteredUsers.length);
  const paginatedUsers = filteredUsers.slice(startIndex, startIndex + itemsPerPage);

  return (
    <section className="contentPage">
      <div className="pageTitleRow">
        <div>
          <p className="eyebrow">Access control</p>
          <h1>Users</h1>
        </div>
        <ProfileDropdown account={account} onLogout={onLogout} />
      </div>

      <section className="metricGrid">
        <article className="metricCard">
          <span className="metricIcon">
            <UsersIcon size={18} />
          </span>
          <div>
            <small>Total Users</small>
            <strong>{users.length}</strong>
          </div>
        </article>
        <article className="metricCard">
          <span className="metricIcon success">
            <ShieldCheck size={18} />
          </span>
          <div>
            <small>Admins</small>
            <strong>{adminCount}</strong>
          </div>
        </article>
      </section>

      {showForm && (
        <section className="panel settingsPanel">
          <div className="panelHeader">
            <h2>Add User</h2>
          </div>
          <form className="authForm" onSubmit={handleSubmit}>
            <div className="userFormGrid">
              <label>
                Full name
                <input
                  name="full_name"
                  onChange={updateField}
                  placeholder="e.g. Priya Sharma"
                  required
                  type="text"
                  value={form.full_name}
                />
              </label>

              <label>
                Email
                <input
                  name="email"
                  onChange={updateField}
                  placeholder="name@company.com"
                  required
                  type="email"
                  value={form.email}
                />
              </label>

              <label className="fullSpan passwordField">
                Password
                <input
                  name="password"
                  onChange={updateField}
                  placeholder="Minimum 8 characters"
                  required
                  type={showPassword ? "text" : "password"}
                  value={form.password}
                />
                <button
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  className="passwordToggle"
                  onClick={() => setShowPassword((current) => !current)}
                  type="button"
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </label>

              <div className="fullSpan">
                <span style={{ display: "block", fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
                  Role
                </span>
                <div className="roleCardGroup">
                  <button
                    className={form.role === "user" ? "roleCard selected" : "roleCard"}
                    onClick={() => setForm((current) => ({ ...current, role: "user" }))}
                    type="button"
                  >
                    <span className="roleCardHeader">
                      <UserRound size={16} />
                      User
                    </span>
                    <small>Module access is assigned below.</small>
                  </button>
                  <button
                    className={form.role === "admin" ? "roleCard selected" : "roleCard"}
                    onClick={() =>
                      setForm((current) => ({
                        ...current,
                        role: "admin",
                        module_access: normalizeModuleAccess("admin", current.module_access),
                      }))
                    }
                    type="button"
                  >
                    <span className="roleCardHeader">
                      <ShieldCheck size={16} />
                      Admin
                    </span>
                    <small>Full access, plus user management</small>
                  </button>
                </div>
              </div>

              <label className="fullSpan">
                Module access
                <ModuleAccessSelect
                  disabled={form.role === "admin"}
                  onChange={(moduleAccess) => setForm((current) => ({ ...current, module_access: moduleAccess }))}
                  value={normalizeModuleAccess(form.role, form.module_access)}
                />
              </label>
            </div>

            {error && <div className="errorBanner">{error}</div>}
            {message && <div className="successBanner">{message}</div>}

            <button className="primaryAction authSubmit" disabled={submitting} type="submit">
              <UserPlus size={16} />
              {submitting ? "Creating..." : "Create User"}
            </button>
          </form>
        </section>
      )}

      <section className="panel">
        <div className="panelHeader usersTableHeader">
          <h2>All Users</h2>
          <div className="usersTableActions">
            <label className="usersSearchField">
              <Search size={15} />
              <input
                onChange={(event) => setSearchText(event.target.value)}
                placeholder="Search by name or email"
                type="search"
                value={searchText}
              />
            </label>
            <button className="secondaryAction filterButton" onClick={() => setShowFilters((current) => !current)} type="button">
              <Filter size={14} />
              Filter
              {activeFilterCount > 0 && <span className="filterCount">{activeFilterCount}</span>}
            </button>
            <button
              className="primaryAction"
              onClick={() => setShowForm((curr) => !curr)}
              type="button"
              style={{ minHeight: "34px", padding: "0 12px", fontSize: "13px" }}
            >
              <UserPlus size={14} />
              {showForm ? "Cancel" : "Add User"}
            </button>
          </div>
        </div>

        {showFilters && (
          <div className="filterPanel usersFilterPanel">
            <div className="filterControls usersFilterControls">
              <label>
                Role
                <select onChange={(event) => setRoleFilter(event.target.value)} value={roleFilter}>
                  <option value="all">All roles</option>
                  <option value="admin">Admin</option>
                  <option value="user">User</option>
                </select>
              </label>

              <label>
                Module access
                <select onChange={(event) => setModuleFilter(event.target.value)} value={moduleFilter}>
                  <option value="all">All module access</option>
                  {MODULE_OPTIONS.map((module) => (
                    <option key={module.value} value={module.value}>{module.label}</option>
                  ))}
                  <option value="none">No module access</option>
                </select>
              </label>

              <button
                className="filterClear"
                disabled={activeFilterCount === 0}
                onClick={() => {
                  setRoleFilter("all");
                  setModuleFilter("all");
                }}
                type="button"
              >
                Clear
              </button>
            </div>
          </div>
        )}

        {error && <div className="errorBanner">{error}</div>}

        <div className="comparisonTableWrap">
          <table className="comparisonTable">
            <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Role</th>
                <th>Module Access</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {paginatedUsers.map((user) => {
                const isSelf = user.id === account?.id;
                const rowBusy = rowActionId === user.id;

                return (
                  <tr key={user.id}>
                    <td>
                      <UserRound size={14} style={{ marginRight: 6, verticalAlign: "text-bottom" }} />
                      {user.full_name}
                    </td>
                    <td>{user.email}</td>
                    <td>
                      <span className={user.role === "admin" ? "badge badgeMatch" : "badge badgeToggle"}>
                        {user.role === "admin" ? "Admin" : "User"}
                      </span>
                    </td>
                    <td><ModuleAccessBadges user={user} /></td>
                    <td>
                      <span className={user.is_active ? "badge badgeMatch" : "badge badgeMismatch"}>
                        {user.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>
                    <td>
                      <div className="tableActionGroup">
                        <button
                          aria-label="Edit user"
                          className="iconAction"
                          disabled={isSelf || rowBusy}
                          onClick={() => openEditUser(user)}
                          title={isSelf ? "You can't edit your own role or status" : "Edit user"}
                          type="button"
                        >
                          <Edit3 size={15} />
                        </button>
                        <button
                          aria-label="Delete user"
                          className="iconAction danger"
                          disabled={isSelf || rowBusy}
                          onClick={() => handleDelete(user)}
                          title={isSelf ? "You can't delete your own account" : "Delete user"}
                          type="button"
                        >
                          <Trash2 size={15} />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {filteredUsers.length > 0 && (
          <div className="paginationRow">
            <span className="paginationInfo">
              Showing {startIndex + 1} {endIndex} of {filteredUsers.length}
            </span>
            <div className="paginationButtons">
              <button
                className="paginationBtn"
                onClick={() => setPage((current) => Math.max(current - 1, 1))}
                disabled={page === 1}
                type="button"
              >
                <ChevronLeft size={14} />
                Prev
              </button>
              <button
                className="paginationBtn"
                onClick={() => setPage((current) => Math.min(current + 1, totalPages))}
                disabled={page === totalPages}
                type="button"
              >
                Next
                <ChevronRight size={14} />
              </button>
            </div>
          </div>
        )}

        {!loading && users.length > 0 && !filteredUsers.length && <p className="emptyText">No users match the current controls.</p>}
        {!loading && !users.length && <p className="emptyText">No users found.</p>}
      </section>

      {editingUser && (
        <div className="logModal" role="dialog" aria-modal="true">
          <form className="logModalPanel userEditModalPanel" onSubmit={handleEditSubmit}>
            <header className="logModalHeader">
              <div>
                <span className="badge badgeToggle">Edit User</span>
                <h2>{editingUser.full_name}</h2>
              </div>
              <button
                aria-label="Close edit user"
                className="iconAction"
                onClick={() => setEditingUser(null)}
                title="Close"
                type="button"
              >
                <XCircle size={17} />
              </button>
            </header>

            <div className="userFormGrid singleColumnForm">
              <label>
                Role
                <select
                  name="role"
                  onChange={(event) =>
                    setEditForm((current) => ({
                      ...current,
                      role: event.target.value,
                      module_access: normalizeModuleAccess(event.target.value, current.module_access),
                    }))
                  }
                  value={editForm.role}
                >
                  <option value="user">User</option>
                  <option value="admin">Admin</option>
                </select>
              </label>

              <label>
                Module access
                <ModuleAccessSelect
                  disabled={editForm.role === "admin"}
                  onChange={(moduleAccess) => setEditForm((current) => ({ ...current, module_access: moduleAccess }))}
                  value={normalizeModuleAccess(editForm.role, editForm.module_access)}
                />
              </label>

              <label>
                Status
                <select
                  name="is_active"
                  onChange={(event) =>
                    setEditForm((current) => ({ ...current, is_active: event.target.value === "true" }))
                  }
                  value={String(editForm.is_active)}
                >
                  <option value="true">Active</option>
                  <option value="false">Inactive</option>
                </select>
              </label>
            </div>

            <div className="actionRow">
              <button className="primaryAction" disabled={rowActionId === editingUser.id} type="submit">
                <Edit3 size={16} />
                {rowActionId === editingUser.id ? "Saving..." : "Save Changes"}
              </button>
              <button className="secondaryAction" onClick={() => setEditingUser(null)} type="button">
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}
    </section>
  );
}