.PHONY: serve atualizar verificar

# Três comandos, e mais nenhum:
#
#   make serve       abrir a aplicação
#   make atualizar   atualizar tudo o que é possível atualizar sozinho
#   make verificar   confirmar que o que está publicado continua de pé
#
# Os scripts em scripts/ continuam a poder ser chamados à mão para trabalho
# cirúrgico (ver `python3 scripts/<nome>.py --help`), mas o dia-a-dia são estes
# três. Uma lista de treze alvos obrigava a saber qual deles corresponde ao que
# se quer fazer; esta não.

RUFF ?= uv run --group dev ruff

serve:
	python3 scripts/serve.py

# Demora, e é suposto demorar: descarrega todas as fontes oficiais, captura
# fotografias em falta, remove campanhas expiradas com a cascata de elegibilidade,
# arruma imagens órfãs, recompila, testa e verifica todas as ligações. No fim diz
# o que ficou por fazer, porque há partes que nenhum script pode decidir.
atualizar:
	@echo "══ 1/8  Lint"
	@$(RUFF) check .
	@echo "\n══ 2/8  Fontes oficiais conhecidas (fingerprints)"
	-@python3 scripts/update_catalog.py
	@echo "\n══ 3/8  Radar de mercado: modelos novos por decidir"
	-@python3 scripts/discover_models.py
	@echo "\n══ 4/8  Fotografias em falta ou inválidas"
	-@python3 scripts/capture_photos.py
	@echo "\n══ 5/8  Campanhas expiradas e elegibilidade"
	@python3 scripts/expire_campaigns.py --apply
	@echo "\n══ 6/8  Imagens que nenhum modelo referencia"
	@python3 scripts/archive_unused_images.py --apply
	@echo "\n══ 7/8  Validar, compilar e testar"
	@python3 scripts/validate_data.py
	@python3 scripts/compile_data.py
	@python3 -m unittest discover -s tests
	@node --test tests/*.test.js
	@echo "\n══ 8/8  Ligações oficiais e concessionários"
	-@python3 scripts/validate_data.py --check-links
	@python3 scripts/report_pending.py

# Sem rede a escrever nada: só confirma o estado atual. É o que corre no CI e o
# que se corre antes de publicar.
verificar:
	@$(RUFF) check .
	@python3 scripts/validate_data.py --check-freshness
	@python3 scripts/compile_data.py
	@python3 -m unittest discover -s tests
	@node --test tests/*.test.js
	@python3 scripts/validate_data.py --check-links
	@python3 scripts/report_pending.py
