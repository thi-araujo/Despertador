"""Despertador com interface gráfica.

    python despertador.py

Os alarmes ficam salvos em ~/.despertador.json e só tocam enquanto o
programa estiver aberto (pode deixar minimizado).
"""

from __future__ import annotations

import platform
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

from alarmes import NOMES_DIAS, SONECA_PADRAO_MIN, Agenda, Alarme, tempo_ate

VERIFICACAO_MS = 500
TOQUE_MAXIMO_MIN = 10  # depois disso, um alarme sem resposta para sozinho

DIAS_EXTENSO = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira",
                "sábado", "domingo"]
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro",
         "outubro", "novembro", "dezembro"]

CORES = {
    "fundo": "#0f172a",
    "painel": "#1e293b",
    "borda": "#334155",
    "texto": "#e2e8f0",
    "texto_suave": "#94a3b8",
    "destaque": "#38bdf8",
    "verde": "#22c55e",
    "vermelho": "#ef4444",
    "ambar": "#f59e0b",
}

WINDOWS = platform.system() == "Windows"
FONTE = "Segoe UI" if WINDOWS else "Helvetica"
FONTE_MONO = "Consolas" if WINDOWS else "DejaVu Sans Mono"


def data_por_extenso(agora: datetime) -> str:
    return f"{DIAS_EXTENSO[agora.weekday()]}, {agora.day} de {MESES[agora.month - 1]}"


def tocar_som(janela: tk.Misc) -> None:
    if WINDOWS:
        import winsound
        winsound.PlaySound("SystemExclamation", winsound.SND_ALIAS | winsound.SND_ASYNC)
    else:
        janela.bell()


def configurar_estilo(raiz: tk.Tk) -> None:
    estilo = ttk.Style(raiz)
    estilo.theme_use("clam")
    sem_borda = dict(bordercolor=CORES["painel"], lightcolor=CORES["painel"], darkcolor=CORES["painel"])
    estilo.configure(".", background=CORES["fundo"], foreground=CORES["texto"], font=(FONTE, 10))
    estilo.configure("TFrame", background=CORES["fundo"])
    estilo.configure("Painel.TFrame", background=CORES["painel"])
    estilo.configure("TLabel", background=CORES["fundo"])
    estilo.configure("Suave.TLabel", foreground=CORES["texto_suave"])
    estilo.configure("Painel.TLabel", background=CORES["painel"])
    estilo.configure("PainelSuave.TLabel", background=CORES["painel"], foreground=CORES["texto_suave"])
    estilo.configure("TButton", background=CORES["borda"], foreground=CORES["texto"], borderwidth=0,
                     padding=(14, 7), font=(FONTE, 10, "bold"))
    estilo.map("TButton", background=[("disabled", CORES["painel"]), ("active", "#475569")],
               foreground=[("disabled", CORES["texto_suave"])])
    estilo.configure("Destaque.TButton", background=CORES["destaque"], foreground=CORES["fundo"])
    estilo.map("Destaque.TButton", background=[("disabled", CORES["painel"]), ("active", "#0ea5e9")])
    estilo.configure("Perigo.TButton", background=CORES["vermelho"], foreground="white")
    estilo.map("Perigo.TButton", background=[("disabled", CORES["painel"]), ("active", "#dc2626")])
    estilo.configure("Soneca.TButton", background=CORES["ambar"], foreground="#1c1917",
                     padding=(18, 10), font=(FONTE, 11, "bold"))
    estilo.map("Soneca.TButton", background=[("active", "#d97706")])
    estilo.configure("Desligar.TButton", background=CORES["verde"], foreground="#052e16",
                     padding=(18, 10), font=(FONTE, 11, "bold"))
    estilo.map("Desligar.TButton", background=[("active", "#16a34a")])
    estilo.configure("Pequeno.TButton", padding=(8, 3), font=(FONTE, 9))
    estilo.configure("TCheckbutton", background=CORES["painel"], foreground=CORES["texto"])
    estilo.map("TCheckbutton", background=[("active", CORES["painel"])],
               indicatorcolor=[("selected", CORES["destaque"]), ("!selected", CORES["fundo"])])
    estilo.configure("TEntry", fieldbackground=CORES["fundo"], foreground=CORES["texto"],
                     insertcolor=CORES["texto"], bordercolor=CORES["borda"], lightcolor=CORES["fundo"],
                     darkcolor=CORES["fundo"])
    estilo.configure("TSpinbox", fieldbackground=CORES["fundo"], foreground=CORES["texto"],
                     arrowcolor=CORES["texto"], background=CORES["borda"], bordercolor=CORES["borda"],
                     lightcolor=CORES["fundo"], darkcolor=CORES["fundo"])
    estilo.configure("Treeview", background=CORES["painel"], fieldbackground=CORES["painel"],
                     foreground=CORES["texto"], borderwidth=0, rowheight=40, font=(FONTE, 11), **sem_borda)
    estilo.configure("Treeview.Heading", background=CORES["borda"], foreground=CORES["texto_suave"],
                     borderwidth=0, font=(FONTE, 9, "bold"), padding=(6, 5))
    estilo.map("Treeview", background=[("selected", CORES["borda"])],
               foreground=[("selected", CORES["destaque"])])
    estilo.configure("Vertical.TScrollbar", background=CORES["borda"], troughcolor=CORES["painel"],
                     borderwidth=0, arrowcolor=CORES["texto_suave"], **sem_borda)
    estilo.map("Vertical.TScrollbar", background=[("disabled", CORES["painel"]), ("active", "#475569")],
               arrowcolor=[("disabled", CORES["painel"])])


class DialogoAlarme(tk.Toplevel):
    """Janela para criar ou editar um alarme. O resultado fica em self.resultado."""

    def __init__(self, pai: tk.Tk, alarme: Alarme | None = None) -> None:
        super().__init__(pai)
        self.title("Editar alarme" if alarme else "Novo alarme")
        self.configure(bg=CORES["painel"], padx=20, pady=18)
        self.resizable(False, False)
        self.transient(pai)
        self.resultado: Alarme | None = None
        base = alarme or Alarme(hora=self._hora_sugerida(), dias=[0, 1, 2, 3, 4])

        hora, minuto = base.hora.split(":")
        self.var_h = tk.StringVar(value=hora)
        self.var_m = tk.StringVar(value=minuto)
        self.var_rotulo = tk.StringVar(value=base.rotulo)
        self.var_dias = [tk.BooleanVar(value=i in base.dias) for i in range(7)]
        self.id_original = alarme.id if alarme else None
        self.ativo_original = alarme.ativo if alarme else True

        ttk.Label(self, text="Horário", style="PainelSuave.TLabel").pack(anchor="w")
        linha = ttk.Frame(self, style="Painel.TFrame")
        linha.pack(anchor="w", pady=(4, 14))
        for var, maximo in ((self.var_h, 23), (self.var_m, 59)):
            ttk.Spinbox(linha, from_=0, to=maximo, textvariable=var, width=3, wrap=True, format="%02.0f",
                        font=(FONTE_MONO, 22)).pack(side="left")
            if var is self.var_h:
                ttk.Label(linha, text=":", style="Painel.TLabel", font=(FONTE_MONO, 22)).pack(side="left",
                                                                                              padx=4)

        ttk.Label(self, text="Nome (opcional)", style="PainelSuave.TLabel").pack(anchor="w")
        entrada = ttk.Entry(self, textvariable=self.var_rotulo, width=32)
        entrada.pack(anchor="w", fill="x", pady=(4, 14), ipady=3)

        ttk.Label(self, text="Repetir", style="PainelSuave.TLabel").pack(anchor="w")
        dias = ttk.Frame(self, style="Painel.TFrame")
        dias.pack(anchor="w", pady=(4, 6))
        for i, nome in enumerate(NOMES_DIAS):
            ttk.Checkbutton(dias, text=nome, variable=self.var_dias[i]).pack(side="left", padx=(0, 6))
        atalhos = ttk.Frame(self, style="Painel.TFrame")
        atalhos.pack(anchor="w", pady=(0, 4))
        for texto, selecao in (("Uma vez", []), ("Dias úteis", [0, 1, 2, 3, 4]),
                               ("Fim de semana", [5, 6]), ("Todos os dias", list(range(7)))):
            ttk.Button(atalhos, text=texto, style="Pequeno.TButton",
                       command=lambda s=selecao: self._marcar_dias(s)).pack(side="left", padx=(0, 4))
        ttk.Label(self, text="Sem nenhum dia marcado, o alarme toca uma vez e se desliga.",
                  style="PainelSuave.TLabel", font=(FONTE, 9)).pack(anchor="w", pady=(2, 16))

        botoes = ttk.Frame(self, style="Painel.TFrame")
        botoes.pack(fill="x")
        ttk.Button(botoes, text="Salvar", style="Destaque.TButton", command=self._salvar).pack(side="right")
        ttk.Button(botoes, text="Cancelar", command=self.destroy).pack(side="right", padx=8)

        self.bind("<Return>", lambda _e: self._salvar())
        self.bind("<Escape>", lambda _e: self.destroy())
        entrada.focus_set()
        self.update_idletasks()
        x = pai.winfo_rootx() + (pai.winfo_width() - self.winfo_width()) // 2
        y = pai.winfo_rooty() + 60
        self.geometry(f"+{x}+{y}")
        self.grab_set()

    @staticmethod
    def _hora_sugerida() -> str:
        agora = datetime.now()
        return f"{(agora.hour + 1) % 24:02d}:00"

    def _marcar_dias(self, selecao: list[int]) -> None:
        for i, var in enumerate(self.var_dias):
            var.set(i in selecao)

    def _salvar(self) -> None:
        try:
            hora = f"{int(self.var_h.get()):02d}:{int(self.var_m.get()):02d}"
            alarme = Alarme(hora=hora, rotulo=self.var_rotulo.get().strip(),
                            dias=[i for i, v in enumerate(self.var_dias) if v.get()])
        except ValueError:
            messagebox.showwarning("Horário inválido", "Use horas de 00 a 23 e minutos de 00 a 59.",
                                   parent=self)
            return
        if self.id_original:
            alarme.id = self.id_original
        self.resultado = alarme
        self.destroy()


class JanelaToque(tk.Toplevel):
    """Janela que aparece quando um alarme toca."""

    def __init__(self, app: "Aplicativo", alarme: Alarme) -> None:
        super().__init__(app)
        self.app = app
        self.alarme = alarme
        self.inicio = datetime.now()
        self._piscar = False
        self.title("Alarme")
        self.configure(bg=CORES["painel"], padx=36, pady=28)
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", self.desligar)

        self.lbl_hora = tk.Label(self, text=datetime.now().strftime("%H:%M"), font=(FONTE_MONO, 56, "bold"),
                                 bg=CORES["painel"], fg=CORES["texto"])
        self.lbl_hora.pack()
        tk.Label(self, text=alarme.rotulo or "Alarme", font=(FONTE, 16, "bold"), bg=CORES["painel"],
                 fg=CORES["destaque"]).pack(pady=(0, 4))
        tk.Label(self, text=f"Programado para {alarme.hora}", font=(FONTE, 10), bg=CORES["painel"],
                 fg=CORES["texto_suave"]).pack(pady=(0, 20))
        botoes = ttk.Frame(self, style="Painel.TFrame")
        botoes.pack()
        ttk.Button(botoes, text=f"Soneca {SONECA_PADRAO_MIN} min", style="Soneca.TButton",
                   command=self.adiar).pack(side="left", padx=6)
        ttk.Button(botoes, text="Desligar", style="Desligar.TButton",
                   command=self.desligar).pack(side="left", padx=6)

        self.update_idletasks()
        x = (self.winfo_screenwidth() - self.winfo_width()) // 2
        y = (self.winfo_screenheight() - self.winfo_height()) // 3
        self.geometry(f"+{x}+{y}")
        self.lift()
        self.focus_force()
        self._tocar()

    def _tocar(self) -> None:
        if not self.winfo_exists():
            return
        if (datetime.now() - self.inicio).total_seconds() > TOQUE_MAXIMO_MIN * 60:
            self.app.registrar_toque_perdido(self.alarme)
            self.desligar()
            return
        self._piscar = not self._piscar
        self.lbl_hora.configure(fg=CORES["vermelho"] if self._piscar else CORES["texto"],
                                text=datetime.now().strftime("%H:%M"))
        tocar_som(self)
        self.after(1000, self._tocar)

    def adiar(self) -> None:
        self.app.adiar(self.alarme)
        self.destroy()

    def desligar(self) -> None:
        self.app.agenda.cancelar_soneca(self.alarme.id)
        self.app.atualizar_lista()
        self.destroy()


class Aplicativo(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Despertador")
        self.geometry("660x600")
        self.minsize(640, 520)
        self.configure(bg=CORES["fundo"])
        configurar_estilo(self)

        self.agenda = Agenda.carregar()
        self.toques: dict[str, JanelaToque] = {}

        # Relógio
        topo = ttk.Frame(self, padding=(20, 18, 20, 6))
        topo.pack(fill="x")
        self.lbl_relogio = tk.Label(topo, font=(FONTE_MONO, 52, "bold"), bg=CORES["fundo"], fg=CORES["texto"])
        self.lbl_relogio.pack()
        self.lbl_data = ttk.Label(topo, style="Suave.TLabel", font=(FONTE, 12))
        self.lbl_data.pack()
        self.lbl_proximo = tk.Label(topo, font=(FONTE, 10, "bold"), bg=CORES["fundo"], fg=CORES["destaque"])
        self.lbl_proximo.pack(pady=(10, 0))

        # Botões
        ttk.Label(self, text="Os alarmes só tocam com o programa aberto (pode deixar minimizado).",
                  style="Suave.TLabel", font=(FONTE, 9)).pack(side="bottom", pady=(4, 12))
        botoes = ttk.Frame(self, padding=(20, 12, 20, 6))
        botoes.pack(side="bottom", fill="x")
        ttk.Button(botoes, text="+ Novo alarme", style="Destaque.TButton", command=self.novo).pack(side="left")
        self.btn_editar = ttk.Button(botoes, text="Editar", command=self.editar)
        self.btn_editar.pack(side="left", padx=(8, 0))
        self.btn_alternar = ttk.Button(botoes, text="Desativar", command=self.alternar)
        self.btn_alternar.pack(side="left", padx=(8, 0))
        self.btn_excluir = ttk.Button(botoes, text="Excluir", style="Perigo.TButton", command=self.excluir)
        self.btn_excluir.pack(side="left", padx=(8, 0))
        ttk.Button(botoes, text="Testar som", command=lambda: tocar_som(self)).pack(side="right")

        # Lista de alarmes
        meio = ttk.Frame(self, padding=(20, 10, 20, 0))
        meio.pack(fill="both", expand=True)
        self.lista = ttk.Treeview(meio, columns=("hora", "nome", "repetir", "status"), show="headings",
                                  selectmode="browse", height=5)
        for coluna, titulo, largura, ancora in (("hora", "Hora", 80, "center"), ("nome", "Nome", 170, "w"),
                                                ("repetir", "Repetir", 160, "w"),
                                                ("status", "Status", 110, "center")):
            self.lista.heading(coluna, text=titulo, anchor=ancora)
            self.lista.column(coluna, width=largura, anchor=ancora, stretch=coluna == "nome")
        self.lista.tag_configure("inativo", foreground=CORES["texto_suave"])
        self.lista.tag_configure("soneca", foreground=CORES["ambar"])
        barra = ttk.Scrollbar(meio, orient="vertical", command=self.lista.yview)
        self.lista.configure(yscrollcommand=barra.set)
        self.lista.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")
        self.lista.bind("<Double-1>", lambda _e: self.editar())
        self.lista.bind("<Delete>", lambda _e: self.excluir())
        self.lista.bind("<space>", lambda _e: self.alternar())
        self.lista.bind("<<TreeviewSelect>>", lambda _e: self._atualizar_botoes())

        self.lbl_vazio = tk.Label(self.lista, text="Nenhum alarme ainda.\nClique em \"Novo alarme\" para criar.",
                                  bg=CORES["painel"], fg=CORES["texto_suave"], font=(FONTE, 11))

        self.protocol("WM_DELETE_WINDOW", self._ao_fechar)
        self.atualizar_lista()
        self._laco()

    # ------------------------------------------------------------------ lista

    def _selecionado(self) -> Alarme | None:
        selecao = self.lista.selection()
        return self.agenda.buscar(selecao[0]) if selecao else None

    def atualizar_lista(self) -> None:
        selecao = self.lista.selection()
        self.lista.delete(*self.lista.get_children())
        for alarme in self.agenda.alarmes:
            soneca = self.agenda.sonecas.get(alarme.id)
            if soneca:
                status, tag = f"Soneca {soneca:%H:%M}", "soneca"
            elif alarme.ativo:
                status, tag = "Ativo", ""
            else:
                status, tag = "Desativado", "inativo"
            self.lista.insert("", "end", iid=alarme.id, tags=(tag,),
                              values=(alarme.hora, alarme.rotulo or "Alarme", alarme.descricao_dias(), status))
        if selecao and self.lista.exists(selecao[0]):
            self.lista.selection_set(selecao[0])
        if self.agenda.alarmes:
            self.lbl_vazio.place_forget()
        else:
            self.lbl_vazio.place(relx=0.5, rely=0.5, anchor="center")
        self._atualizar_botoes()
        self._atualizar_proximo()

    def _atualizar_botoes(self) -> None:
        alarme = self._selecionado()
        estado = ["!disabled"] if alarme else ["disabled"]
        for botao in (self.btn_editar, self.btn_alternar, self.btn_excluir):
            botao.state(estado)
        self.btn_alternar.configure(text="Desativar" if alarme and alarme.ativo else "Ativar")

    def _atualizar_proximo(self) -> None:
        agora = datetime.now()
        proximo = self.agenda.proximo(agora)
        if proximo is None:
            self.lbl_proximo.configure(text="Nenhum alarme ativo", fg=CORES["texto_suave"])
            return
        alarme, quando = proximo
        nome = f" ({alarme.rotulo})" if alarme.rotulo else ""
        self.lbl_proximo.configure(text=f"Próximo alarme: {quando:%H:%M}{nome}, {tempo_ate(quando, agora)}",
                                   fg=CORES["destaque"])

    def _salvar(self) -> None:
        try:
            self.agenda.salvar()
        except OSError as erro:
            messagebox.showerror("Despertador", f"Não foi possível salvar os alarmes:\n{erro}", parent=self)

    # ------------------------------------------------------------------ ações

    def novo(self) -> None:
        dialogo = DialogoAlarme(self)
        self.wait_window(dialogo)
        if dialogo.resultado:
            self.agenda.adicionar(dialogo.resultado)
            self._salvar()
            self.atualizar_lista()
            self.lista.selection_set(dialogo.resultado.id)

    def editar(self) -> None:
        alarme = self._selecionado()
        if not alarme:
            return
        dialogo = DialogoAlarme(self, alarme)
        self.wait_window(dialogo)
        if dialogo.resultado:
            self.agenda.remover(alarme.id)
            dialogo.resultado.ativo = True  # editar um alarme o reativa
            self.agenda.adicionar(dialogo.resultado)
            self._salvar()
            self.atualizar_lista()

    def alternar(self) -> None:
        alarme = self._selecionado()
        if not alarme:
            return
        alarme.ativo = not alarme.ativo
        if not alarme.ativo:
            self.agenda.cancelar_soneca(alarme.id)
        self._salvar()
        self.atualizar_lista()

    def excluir(self) -> None:
        alarme = self._selecionado()
        if not alarme:
            return
        nome = alarme.rotulo or "Alarme"
        if messagebox.askyesno("Excluir alarme", f"Excluir \"{nome}\" das {alarme.hora}?", parent=self):
            self.agenda.remover(alarme.id)
            self._salvar()
            self.atualizar_lista()

    def adiar(self, alarme: Alarme) -> None:
        self.agenda.adiar(alarme.id, datetime.now())
        self.atualizar_lista()

    def registrar_toque_perdido(self, alarme: Alarme) -> None:
        nome = alarme.rotulo or "Alarme"
        self.lbl_proximo.configure(text=f"{nome} das {alarme.hora} tocou sem resposta", fg=CORES["ambar"])

    # ------------------------------------------------------------------ laço

    def _laco(self) -> None:
        agora = datetime.now()
        self.lbl_relogio.configure(text=agora.strftime("%H:%M:%S"))
        self.lbl_data.configure(text=data_por_extenso(agora))

        disparados = self.agenda.verificar(agora)
        if disparados:
            self._salvar()  # alarmes de uma vez foram desativados
            self.atualizar_lista()
            for alarme in disparados:
                janela = self.toques.get(alarme.id)
                if janela is not None and janela.winfo_exists():
                    continue
                self.toques[alarme.id] = JanelaToque(self, alarme)
        self._atualizar_proximo()
        self.after(VERIFICACAO_MS, self._laco)

    def _ao_fechar(self) -> None:
        if any(a.ativo for a in self.agenda.alarmes) or self.agenda.sonecas:
            if not messagebox.askyesno(
                "Fechar Despertador",
                "Com o programa fechado, os alarmes não tocam.\n"
                "Dica: minimize a janela em vez de fechar.\n\nFechar mesmo assim?",
                parent=self,
            ):
                return
        self.destroy()


def main() -> None:
    Aplicativo().mainloop()


if __name__ == "__main__":
    main()
