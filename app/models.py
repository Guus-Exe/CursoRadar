"""Data models for Senac Monitor."""

from datetime import datetime
import hashlib
import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class OfferState(BaseModel):
    """Normalized state of a Senac course offer."""

    curso: str = Field(default="", description="Nome do curso")
    unidade: str = Field(default="", description="Unidade do Senac")
    turno: str = Field(default="", description="Turno ou período das aulas")
    status: str = Field(default="Indisponível", description="Status descritivo da oferta")
    bolsa_disponivel: bool = Field(default=False, description="Se há bolsa disponível")
    inscricao_disponivel: bool = Field(default=False, description="Se a inscrição/matrícula está aberta")
    datas: List[str] = Field(default_factory=list, description="Datas relevantes (início, término, abertura)")
    horarios: List[str] = Field(default_factory=list, description="Horários e dias das aulas")
    botoes: List[str] = Field(default_factory=list, description="Botões de ação identificados na página")
    texto_relevante: List[str] = Field(default_factory=list, description="Mensagens ou observações textuais importantes")

    # Metadados adicionais úteis
    codigo_oferta: Optional[str] = Field(default=None, description="Código único da oferta (ex: 9900357333)")
    url: Optional[str] = Field(default=None, description="URL da oferta")
    vagas_totais: Optional[int] = Field(default=None, description="Quantidade total de vagas")
    vagas_bolsa: Optional[int] = Field(default=None, description="Quantidade de vagas para bolsa")
    preco: Optional[str] = Field(default=None, description="Valor do curso ou parcelas")

    def to_normalized_dict(self) -> Dict[str, Any]:
        """Returns the exact normalized dictionary required by the user."""
        return {
            "curso": self.curso,
            "unidade": self.unidade,
            "turno": self.turno,
            "status": self.status,
            "bolsa_disponivel": self.bolsa_disponivel,
            "inscricao_disponivel": self.inscricao_disponivel,
            "datas": self.datas,
            "horarios": self.horarios,
            "botoes": self.botoes,
            "texto_relevante": self.texto_relevante,
        }

    def compute_state_hash(self) -> str:
        """Calculates a deterministic MD5 hash of the normalized state for deduplication."""
        norm = self.to_normalized_dict()
        serialized = json.dumps(norm, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(serialized.encode("utf-8")).hexdigest()

    def compute_alert_hash(self) -> str:
        """Calculates a hash specifically for actionable alerts to prevent duplicate notifications."""
        key_data = {
            "status": self.status,
            "bolsa_disponivel": self.bolsa_disponivel,
            "inscricao_disponivel": self.inscricao_disponivel,
            "botoes": sorted(self.botoes),
            "datas": sorted(self.datas),
            "horarios": sorted(self.horarios),
        }
        serialized = json.dumps(key_data, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(serialized.encode("utf-8")).hexdigest()


class StateDiff(BaseModel):
    """Represents detected differences between two states."""

    has_changed: bool = False
    is_actionable: bool = False
    reasons: List[str] = Field(default_factory=list)
    previous_state: Optional[OfferState] = None
    current_state: OfferState
    detected_at: datetime = Field(default_factory=datetime.now)

    def summary(self) -> str:
        """User-friendly summary of the detected changes."""
        if not self.has_changed:
            return "Nenhuma alteração relevante detectada."
        return "\n".join(f"• {r}" for r in self.reasons)


class DiscoveredOffer(BaseModel):
    """Represents a discovered offer from search."""

    codigo_oferta: str
    curso: str
    unidade: str
    turno: str
    url: str
    data_inicio: Optional[str] = None
    horario: Optional[str] = None
    vagas_disponiveis: bool = False
    bolsa_disponivel: bool = False
    descoberto_em: datetime = Field(default_factory=datetime.now)
