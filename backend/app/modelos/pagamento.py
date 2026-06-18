from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.banco.conexao import BaseModelo


def data_atual():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ConfiguracaoPagamento(BaseModelo):
    __tablename__ = "payment_settings"
    __table_args__ = (
        CheckConstraint(
            "provedor IN ('manual', 'mercado_pago', 'asaas', 'efi')",
            name="ck_payment_settings_provedor",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    provedor: Mapped[str] = mapped_column(String(40), default="manual")
    chave_pix_criptografada: Mapped[bytes] = mapped_column(LargeBinary)
    token_api_criptografado: Mapped[bytes | None] = mapped_column(
        LargeBinary,
        nullable=True,
    )
    client_id_criptografado: Mapped[bytes | None] = mapped_column(
        LargeBinary,
        nullable=True,
    )
    client_secret_criptografado: Mapped[bytes | None] = mapped_column(
        LargeBinary,
        nullable=True,
    )
    segredo_webhook_criptografado: Mapped[bytes | None] = mapped_column(
        LargeBinary,
        nullable=True,
    )
    token_webhook: Mapped[str | None] = mapped_column(
        String(80),
        unique=True,
        nullable=True,
        index=True,
    )
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    data_atualizacao: Mapped[datetime] = mapped_column(
        DateTime,
        default=data_atual,
        onupdate=data_atual,
    )


class EventoWebhookPagamento(BaseModelo):
    __tablename__ = "payment_webhook_events"
    __table_args__ = (
        UniqueConstraint(
            "empresa_id",
            "provedor",
            "evento_externo_id",
            name="uq_payment_webhook_evento_empresa",
        ),
        ForeignKeyConstraint(
            ["venda_id", "empresa_id"],
            ["sales.id", "sales.empresa_id"],
            name="fk_payment_webhook_venda_empresa",
            ondelete="RESTRICT",
        ),
        Index(
            "ix_payment_webhook_empresa_data",
            "empresa_id",
            "data_recebimento",
        ),
        Index(
            "ix_payment_webhook_cobranca",
            "empresa_id",
            "provedor",
            "cobranca_externa_id",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"),
        index=True,
    )
    venda_id: Mapped[int | None] = mapped_column(nullable=True, index=True)
    provedor: Mapped[str] = mapped_column(String(40))
    evento_externo_id: Mapped[str] = mapped_column(String(180))
    cobranca_externa_id: Mapped[str] = mapped_column(String(180))
    tipo: Mapped[str] = mapped_column(String(80), default="payment")
    status: Mapped[str] = mapped_column(String(30), default="recebido")
    hash_payload: Mapped[str] = mapped_column(String(64))
    mensagem: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_recebimento: Mapped[datetime] = mapped_column(
        DateTime,
        default=data_atual,
    )
    data_processamento: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
