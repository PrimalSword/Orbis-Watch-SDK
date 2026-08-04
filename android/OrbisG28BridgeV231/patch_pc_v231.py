from pathlib import Path
import re

PC = Path('pc/orbis_g28_bridge/orbis_g28_pc.py')
text = PC.read_text(encoding='utf-8')

pattern = r'    def _final_reboot\(self\) -> None:\n.*?(?=    def _append\(self, text: str\) -> None:)'
replacement = '''    def _final_reboot(self) -> None:
        confirmed = messagebox.askyesno(
            "Tentativa final D5/0E",
            """Enviar agora o comando D5/0E?

Ele não transmite firmware nem tabela de partições. Ele encerra/reinicia a sessão OTA e pode desconectar o relógio imediatamente.

Use somente uma vez. Se o G28 voltar no endereço terminado em :02, a tentativa falhou e o projeto será encerrado.""",
        )
        if confirmed:
            self._send("finalize_reboot")

'''
text, count = re.subn(pattern, lambda _: replacement, text, count=1, flags=re.S)
if count != 1:
    raise SystemExit('final reboot PC method not found')
PC.write_text(text, encoding='utf-8')
