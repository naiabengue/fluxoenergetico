"""Corpo do pedido de revisão diário (lido pelo proprietário no telemóvel)."""
import json
import sys

s = json.load(open(sys.argv[1], encoding="utf-8"))
print("Rascunhos gerados hoje. Para publicar: rever o texto e as fontes e fazer *Merge*. Para rejeitar: fechar o pedido.\n")
for r in s["review"]:
    print(f"- **{r['title']}** — pontuação {r.get('score', '—')}; fonte: {r.get('source', 'dados oficiais')}")
print("\n**Antes de aprovar, confirmar:**")
print("- [ ] Os números e datas batem certo com a fonte original")
print("- [ ] Não há conclusões que a fonte não sustente")
print("- [ ] O título não exagera")
print("\nAo aprovar, o artigo é publicado com a nota de texto com apoio de IA revisto pela redação.")
