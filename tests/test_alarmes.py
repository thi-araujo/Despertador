import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from alarmes import Agenda, Alarme, tempo_ate, texto_para_hora  # noqa: E402

# 16/11/2026 é uma segunda-feira.
SEGUNDA_6H = datetime(2026, 11, 16, 6, 0, 0)


class TestAlarme(unittest.TestCase):
    def test_normaliza_hora_e_dias(self):
        alarme = Alarme(hora="7:5", dias=[4, 0, 0, 9])
        self.assertEqual(alarme.hora, "07:05")
        self.assertEqual(alarme.dias, [0, 4])

    def test_hora_invalida(self):
        for texto in ["25:00", "7h", "", "07:60"]:
            with self.assertRaises(ValueError, msg=texto):
                Alarme(hora=texto)

    def test_proximo_disparo_uma_vez(self):
        alarme = Alarme(hora="07:00")
        self.assertEqual(alarme.proximo_disparo(SEGUNDA_6H), datetime(2026, 11, 16, 7, 0))
        # Depois das 7h, vai para o dia seguinte.
        self.assertEqual(alarme.proximo_disparo(SEGUNDA_6H.replace(hour=8)), datetime(2026, 11, 17, 7, 0))

    def test_proximo_disparo_dias_uteis(self):
        alarme = Alarme(hora="07:00", dias=[0, 1, 2, 3, 4])
        sexta_8h = datetime(2026, 11, 20, 8, 0)
        self.assertEqual(alarme.proximo_disparo(sexta_8h), datetime(2026, 11, 23, 7, 0))  # segunda

    def test_minuto_atual_conta(self):
        alarme = Alarme(hora="07:00")
        self.assertEqual(alarme.proximo_disparo(datetime(2026, 11, 16, 7, 0, 30)),
                         datetime(2026, 11, 16, 7, 0))

    def test_desativado_nao_tem_proximo(self):
        self.assertIsNone(Alarme(hora="07:00", ativo=False).proximo_disparo(SEGUNDA_6H))

    def test_descricao_dias(self):
        self.assertEqual(Alarme(dias=[]).descricao_dias(), "Uma vez")
        self.assertEqual(Alarme(dias=[0, 1, 2, 3, 4]).descricao_dias(), "Dias úteis")
        self.assertEqual(Alarme(dias=[5, 6]).descricao_dias(), "Fim de semana")
        self.assertEqual(Alarme(dias=[0, 2]).descricao_dias(), "Seg, Qua")


class TestAgenda(unittest.TestCase):
    def rodar(self, agenda, inicio, segundos, passo=1):
        """Simula a verificação a cada `passo` segundos e devolve os disparos."""
        disparos = []
        for s in range(0, segundos, passo):
            agora = inicio + timedelta(seconds=s)
            disparos += [(agora, a.rotulo) for a in agenda.verificar(agora)]
        return disparos

    def test_toca_uma_vez_no_minuto(self):
        agenda = Agenda([Alarme(hora="06:01", rotulo="acordar", dias=list(range(7)))])
        disparos = self.rodar(agenda, SEGUNDA_6H, 180)
        self.assertEqual(disparos, [(datetime(2026, 11, 16, 6, 1, 0), "acordar")])

    def test_nao_perde_alarme_com_verificacao_atrasada(self):
        agenda = Agenda([Alarme(hora="06:01", rotulo="acordar")])
        agenda.verificar(datetime(2026, 11, 16, 6, 0, 58))
        # Próxima verificação só 10 s depois: o alarme das 06:01 ainda toca.
        self.assertEqual(len(agenda.verificar(datetime(2026, 11, 16, 6, 1, 8))), 1)

    def test_nao_toca_alarme_que_ja_passou_ao_abrir(self):
        agenda = Agenda([Alarme(hora="05:59")])
        self.assertEqual(agenda.verificar(SEGUNDA_6H), [])

    def test_alarme_unico_se_desliga(self):
        alarme = Alarme(hora="06:00")
        agenda = Agenda([alarme])
        self.assertEqual(agenda.verificar(SEGUNDA_6H), [alarme])
        self.assertFalse(alarme.ativo)

    def test_repetido_continua_ativo(self):
        alarme = Alarme(hora="06:00", dias=[0])
        agenda = Agenda([alarme])
        agenda.verificar(SEGUNDA_6H)
        self.assertTrue(alarme.ativo)
        self.assertEqual(agenda.proximo(SEGUNDA_6H + timedelta(minutes=1))[1], datetime(2026, 11, 23, 6, 0))

    def test_soneca(self):
        alarme = Alarme(hora="06:00", rotulo="acordar", dias=list(range(7)))
        agenda = Agenda([alarme])
        agenda.verificar(SEGUNDA_6H)
        quando = agenda.adiar(alarme.id, SEGUNDA_6H, minutos=5)
        self.assertEqual(quando, datetime(2026, 11, 16, 6, 5))
        self.assertEqual(agenda.proximo(SEGUNDA_6H), (alarme, quando))
        disparos = self.rodar(agenda, SEGUNDA_6H + timedelta(seconds=1), 400)
        self.assertEqual(disparos, [(datetime(2026, 11, 16, 6, 5), "acordar")])

    def test_cancelar_soneca(self):
        alarme = Alarme(hora="06:00")
        agenda = Agenda([alarme])
        self.assertEqual(agenda.verificar(SEGUNDA_6H), [alarme])  # toca às 06:00
        agenda.adiar(alarme.id, SEGUNDA_6H)
        agenda.cancelar_soneca(alarme.id)
        self.assertEqual(self.rodar(agenda, SEGUNDA_6H + timedelta(seconds=1), 600, passo=5), [])

    def test_ignora_disparos_perdidos_apos_suspensao(self):
        agenda = Agenda([Alarme(hora="06:30")])
        agenda.verificar(SEGUNDA_6H)
        self.assertEqual(agenda.verificar(SEGUNDA_6H + timedelta(hours=2)), [])

    def test_proximo_escolhe_o_mais_cedo(self):
        a = Alarme(hora="08:00", rotulo="a")
        b = Alarme(hora="06:30", rotulo="b")
        agenda = Agenda()
        agenda.adicionar(a)
        agenda.adicionar(b)
        self.assertEqual([x.rotulo for x in agenda.alarmes], ["b", "a"])  # ordenados por hora
        self.assertEqual(agenda.proximo(SEGUNDA_6H)[0], b)
        self.assertIsNone(Agenda().proximo(SEGUNDA_6H))

    def test_salvar_e_carregar(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "alarmes.json"
            agenda = Agenda()
            agenda.adicionar(Alarme(hora="07:15", rotulo="Academia", dias=[0, 2, 4]))
            agenda.adicionar(Alarme(hora="22:00", ativo=False))
            agenda.salvar(arquivo)
            carregada = Agenda.carregar(arquivo)
            self.assertEqual(carregada.alarmes, agenda.alarmes)

    def test_arquivo_corrompido(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "alarmes.json"
            arquivo.write_text('{"alarmes": [{"hora": "99:99"}, {"hora": "06:00"}]}', encoding="utf-8")
            self.assertEqual([a.hora for a in Agenda.carregar(arquivo).alarmes], ["06:00"])
            arquivo.write_text("lixo", encoding="utf-8")
            self.assertEqual(Agenda.carregar(arquivo).alarmes, [])


class TestTexto(unittest.TestCase):
    def test_tempo_ate(self):
        self.assertEqual(tempo_ate(SEGUNDA_6H + timedelta(seconds=30), SEGUNDA_6H), "em menos de 1 min")
        self.assertEqual(tempo_ate(SEGUNDA_6H + timedelta(hours=7, minutes=23), SEGUNDA_6H), "em 7 h 23 min")
        self.assertEqual(tempo_ate(SEGUNDA_6H + timedelta(minutes=45), SEGUNDA_6H), "em 45 min")
        self.assertEqual(tempo_ate(SEGUNDA_6H + timedelta(days=2, hours=3), SEGUNDA_6H), "em 2 d 3 h")

    def test_texto_para_hora(self):
        self.assertEqual(texto_para_hora(" 6:30 ").minute, 30)


if __name__ == "__main__":
    unittest.main()
