"""Lógica do despertador: alarmes, repetição por dia da semana e soneca.

Não depende da interface gráfica. As funções recebem o horário atual por
parâmetro, o que permite testá-las com qualquer data.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, time, timedelta
from pathlib import Path

ARQUIVO_ALARMES = Path.home() / ".despertador.json"
NOMES_DIAS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
SONECA_PADRAO_MIN = 5


def texto_para_hora(texto: str) -> time:
    """Converte "7:05" ou "07:05" em time. Levanta ValueError se for inválido."""
    partes = texto.strip().split(":")
    if len(partes) != 2 or not all(p.isdigit() for p in partes):
        raise ValueError(f"horário inválido: {texto}")
    return time(int(partes[0]), int(partes[1]))


@dataclass
class Alarme:
    hora: str = "07:00"
    rotulo: str = ""
    dias: list[int] = field(default_factory=list)  # vazio = toca uma vez só
    ativo: bool = True
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    def __post_init__(self) -> None:
        h = texto_para_hora(self.hora)
        self.hora = f"{h.hour:02d}:{h.minute:02d}"
        self.dias = sorted({int(d) for d in self.dias if 0 <= int(d) <= 6})

    @property
    def repete(self) -> bool:
        return bool(self.dias)

    def proximo_disparo(self, agora: datetime) -> datetime | None:
        """Próxima data e hora em que o alarme toca, contando a partir de `agora`.

        Um disparo exatamente no minuto atual conta como próximo, para o
        alarme não ser pulado se a verificação cair no segundo 0.
        """
        if not self.ativo:
            return None
        h = texto_para_hora(self.hora)
        inicio_minuto = agora.replace(second=0, microsecond=0)
        for adiante in range(8):
            dia = (agora + timedelta(days=adiante)).date()
            candidato = datetime.combine(dia, h)
            if candidato < inicio_minuto:
                continue
            if not self.dias or candidato.weekday() in self.dias:
                return candidato
        return None

    def descricao_dias(self) -> str:
        if not self.dias:
            return "Uma vez"
        if self.dias == list(range(7)):
            return "Todos os dias"
        if self.dias == [0, 1, 2, 3, 4]:
            return "Dias úteis"
        if self.dias == [5, 6]:
            return "Fim de semana"
        return ", ".join(NOMES_DIAS[d] for d in self.dias)


def tempo_ate(destino: datetime, agora: datetime) -> str:
    """Texto curto como "em 7 h 23 min" ou "em menos de 1 min"."""
    minutos = int((destino - agora).total_seconds() // 60)
    if minutos < 1:
        return "em menos de 1 min"
    dias, resto = divmod(minutos, 24 * 60)
    horas, mins = divmod(resto, 60)
    partes = []
    if dias:
        partes.append(f"{dias} d")
    if horas:
        partes.append(f"{horas} h")
    if mins and not dias:
        partes.append(f"{mins} min")
    return "em " + " ".join(partes)


class Agenda:
    """Conjunto de alarmes e sonecas, com controle do que já tocou.

    `verificar(agora)` devolve os alarmes que devem tocar naquele momento.
    Cada alarme toca no máximo uma vez por minuto programado, mesmo que a
    verificação rode várias vezes dentro desse minuto.
    """

    def __init__(self, alarmes: list[Alarme] | None = None) -> None:
        self.alarmes: list[Alarme] = alarmes or []
        self.sonecas: dict[str, datetime] = {}  # id do alarme -> quando tocar de novo
        self._ultimo_disparo: dict[str, datetime] = {}
        self._ultima_verificacao: datetime | None = None

    def adicionar(self, alarme: Alarme) -> None:
        self.alarmes.append(alarme)
        self.alarmes.sort(key=lambda a: a.hora)

    def remover(self, id_alarme: str) -> None:
        self.alarmes = [a for a in self.alarmes if a.id != id_alarme]
        self.sonecas.pop(id_alarme, None)

    def buscar(self, id_alarme: str) -> Alarme | None:
        return next((a for a in self.alarmes if a.id == id_alarme), None)

    def adiar(self, id_alarme: str, agora: datetime, minutos: int = SONECA_PADRAO_MIN) -> datetime:
        quando = agora.replace(microsecond=0) + timedelta(minutes=minutos)
        self.sonecas[id_alarme] = quando
        return quando

    def cancelar_soneca(self, id_alarme: str) -> None:
        self.sonecas.pop(id_alarme, None)

    def verificar(self, agora: datetime) -> list[Alarme]:
        """Alarmes que devem tocar agora (programados ou vindos da soneca).

        Considera tudo o que venceu desde a última verificação, para não
        perder um alarme se o computador travar ou a verificação atrasar
        alguns segundos. Depois de mais de 5 minutos sem verificar (ex.: o
        computador estava suspenso), os disparos perdidos são ignorados.
        """
        desde = self._ultima_verificacao
        if desde is None or agora - desde > timedelta(minutes=5) or desde > agora:
            desde = agora.replace(second=0, microsecond=0) - timedelta(microseconds=1)
        self._ultima_verificacao = agora

        tocar: list[Alarme] = []
        for alarme in self.alarmes:
            soneca = self.sonecas.get(alarme.id)
            if soneca is not None:
                if soneca <= agora:
                    del self.sonecas[alarme.id]
                    tocar.append(alarme)
                continue
            if not alarme.ativo:
                continue
            disparo = alarme.proximo_disparo(desde)
            if (disparo is None or not desde < disparo <= agora
                    or self._ultimo_disparo.get(alarme.id) == disparo):
                continue
            self._ultimo_disparo[alarme.id] = disparo
            if not alarme.repete:
                alarme.ativo = False  # alarme de uma vez se desliga depois de tocar
            tocar.append(alarme)
        return tocar

    def proximo(self, agora: datetime) -> tuple[Alarme, datetime] | None:
        """O próximo alarme a tocar, incluindo sonecas."""
        opcoes: list[tuple[datetime, Alarme]] = []
        for alarme in self.alarmes:
            quando = self.sonecas.get(alarme.id) or alarme.proximo_disparo(agora)
            if quando is not None:
                opcoes.append((quando, alarme))
        if not opcoes:
            return None
        quando, alarme = min(opcoes, key=lambda par: par[0])
        return alarme, quando

    # ------------------------------------------------------------- arquivo

    def salvar(self, caminho: Path = ARQUIVO_ALARMES) -> None:
        dados = {"alarmes": [asdict(a) for a in self.alarmes]}
        caminho.write_text(json.dumps(dados, indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def carregar(cls, caminho: Path = ARQUIVO_ALARMES) -> "Agenda":
        try:
            dados = json.loads(caminho.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        alarmes = []
        for item in dados.get("alarmes", []) if isinstance(dados, dict) else []:
            try:
                alarmes.append(Alarme(**{k: item[k] for k in ("hora", "rotulo", "dias", "ativo", "id")
                                         if k in item}))
            except (TypeError, ValueError):
                continue
        agenda = cls()
        for alarme in alarmes:
            agenda.adicionar(alarme)
        return agenda
