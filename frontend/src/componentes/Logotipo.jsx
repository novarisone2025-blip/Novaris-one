export function Logotipo({ compacto = false }) {
  return (
    <div className={`logotipo ${compacto ? "logotipo-compacto" : ""}`}>
      <span className="simbolo-logotipo">N</span>
      {!compacto && (
        <div>
          <strong>Novaris</strong>
          <small>ONE</small>
        </div>
      )}
    </div>
  );
}
