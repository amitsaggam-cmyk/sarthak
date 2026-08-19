export default function TopNavbar({ title }) {
  return (
    <header className="pageTitleRow authNavbar">
      <div>
        <p className="eyebrow">JADE background verification</p>
        <h1>{title}</h1>
      </div>
    </header>
  );
}
