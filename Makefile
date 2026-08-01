.PHONY: serve atualizar verificar

# Três comandos, e mais nenhum:
#
#   make serve       abrir a aplicação
#   make atualizar   atualizar tudo o que é possível atualizar sozinho
#   make verificar   confirmar que o que está publicado continua de pé
#
# Os scripts em scripts/ continuam a poder ser chamados à mão para trabalho
# cirúrgico (ver `python3 -u scripts/<nome>.py --help`), mas o dia-a-dia são estes
# três. Uma lista de treze alvos obrigava a saber qual deles corresponde ao que
# se quer fazer; esta não.

# python3 -u em todo o lado: sem isso o stdout fica em buffer quando a saída
# não é um terminal, e `make atualizar` passa quinze minutos calado a parecer
# pendurado. Nota sobre -u: é a diferença entre acompanhar e adivinhar.
RUFF ?= uv run --group dev ruff

serve:
	python3 -u scripts/serve.py

# Demora, e é suposto demorar: descarrega todas as fontes oficiais, captura
# fotografias em falta, remove campanhas expiradas com a cascata de elegibilidade,
# arruma imagens órfãs, recompila, testa e verifica todas as ligações. No fim diz
# o que ficou por fazer, porque há partes que nenhum script pode decidir.
atualizar:
	@echo "══ 1/9  Lint"
	@$(RUFF) check .
	@echo "\n══ 2/9  Fontes oficiais conhecidas (fingerprints)"
	-@python3 -u scripts/update_catalog.py
	@echo "\n══ 3/9  Radar de mercado: modelos novos por decidir"
	-@python3 -u scripts/discover_models.py
# Ler os preços num browser real ANTES de expirar seja o que for. Ao contrário,
# uma campanha renovada em agosto seria apagada por a validade de julho ter
# passado, e o carro sairia do catálogo por uma renovação que ninguém leu.
	@echo "\n══ 4/9  Preços e campanhas nas páginas oficiais (browser real)"
	-@python3 -u scripts/refresh_prices.py --apply
	@echo "\n══ 5/9  Fotografias em falta ou inválidas"
	-@python3 -u scripts/capture_photos.py
	@echo "\n══ 6/9  Campanhas ainda expiradas e elegibilidade"
	@python3 -u scripts/expire_campaigns.py --apply
	@echo "\n══ 7/9  Imagens: recomprimir as pesadas e arrumar as órfãs"
	-@python3 -u scripts/optimize_images.py --apply
	@python3 -u scripts/archive_unused_images.py --apply
	@echo "\n══ 8/9  Validar, compilar e testar"
	@python3 -u scripts/validate_data.py
	@python3 -u scripts/compile_data.py
	@python3 -u -m unittest discover -s tests
	@node --test tests/*.test.js
	@echo "\n══ 9/9  Ligações oficiais e concessionários"
	-@python3 -u scripts/validate_data.py --check-links
	@python3 -u scripts/report_pending.py

# Sem rede a escrever nada: só confirma o estado atual. É o que corre no CI e o
# que se corre antes de publicar.
verificar:
	@$(RUFF) check .
	@python3 -u scripts/validate_data.py --check-freshness
	@python3 -u scripts/compile_data.py
	@python3 -u -m unittest discover -s tests
	@node --test tests/*.test.js
	@python3 -u scripts/validate_data.py --check-links
	@python3 -u scripts/report_pending.py
