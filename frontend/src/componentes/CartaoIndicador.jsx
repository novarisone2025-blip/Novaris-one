export function CartaoIndicador({ titulo, valor, descricao, icone: Icone, cor }) {
  return (
    <article className="cartao-indicador">
      <div className={`icone-indicador ${cor}`}>
        <Icone size={21} />
      </div>
      <div>
        <span>{titulo}</span>
        <strong>{valor}</strong>
        <small>{descricao}</small>
      </div>
    </article>
  );
}
