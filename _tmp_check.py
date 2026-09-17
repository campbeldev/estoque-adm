import sqlite3
c = sqlite3.connect("instance/estoque.db")
for t in ["usuario","categoria","obra","item","movimentacao","funcionario","nota","setor","entregador","remessa","evento_remessa"]:
    n = c.execute(f"select count(*) from {t}").fetchone()[0]
    print(f"{t:15} {n}")
