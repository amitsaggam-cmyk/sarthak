import { useState, useRef, useEffect } from "react";
import { LogOut, Shield } from "lucide-react";

export default function ProfileDropdown({ account, onLogout }) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef(null);

  const initials = account?.full_name
    ?.split(" ")
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase() || "HR";

  useEffect(() => {
    function handleClickOutside(event) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div className="profileDropdownContainer" ref={dropdownRef}>
      <button
        className="profileDropdownTrigger"
        onClick={() => setIsOpen(!isOpen)}
        aria-haspopup="true"
        aria-expanded={isOpen}
        type="button"
      >
        {initials}
      </button>
      {isOpen && (
        <div className="profileDropdownMenu">
          <div className="profileDropdownHeader">
            <span className="profileDropdownAvatar">{initials}</span>
            <div className="profileDropdownUserDetails">
              <strong>{account?.full_name || "HR User"}</strong>
              <span className="profileDropdownEmail">{account?.email || "No email"}</span>
            </div>
          </div>
          <div className="profileDropdownBody">
            <div className="profileDropdownItem">
              <Shield size={14} />
              <span>{account?.role === "admin" ? "Administrator" : "Standard User"}</span>
            </div>
          </div>
          <div className="profileDropdownDivider" />
          <button className="profileDropdownLogout" onClick={onLogout} type="button">
            <LogOut size={14} />
            Logout
          </button>
        </div>
      )}
    </div>
  );
}
