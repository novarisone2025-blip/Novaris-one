import { ArrowLeft } from "lucide-react";


export function BotaoVoltar({ aoClicar }) {
  return (
    <button className="botao-voltar" type="button" onClick={aoClicar}>
      <ArrowLeft size={17} />
      Voltar para o login
    </button>
  );
}
