.PHONY: serve update atualizar update-accept update-photos update-photos-all prune-images
.PHONY: sequential verificar verify lint validate test links budgets freshness audit

# python3 -u em todo o lado: sem isso o stdout fica em buffer quando a saída não
# é um terminal, e uma atualização passa minutos calada a parecer pendurada.
PYTHON ?= python3
NODE ?= node
RUFF ?= $(shell command -v uv >/dev/null 2>&1 && echo "uv run --group dev ruff" || echo "ruff")

serve:
	$(PYTHON) -u scripts/serve.py

# Atualização completa. Qualquer erro para o fluxo: sobretudo uma falha de
# refresh_prices, que nunca pode ser convertida em sucesso por `-` no Make.
update:
	@echo "══ 1/9  Lint"
	@$(RUFF) check .
	@echo "\n══ 2/9  Fontes oficiais conhecidas (fingerprints)"
	$(PYTHON) -u scripts/update_catalog.py
	@echo "\n══ 3/9  Radar de mercado: modelos novos por decidir"
	$(PYTHON) -u scripts/discover_models.py
	@echo "\n══ 4/9  Preços e campanhas nas páginas oficiais (browser real)"
	$(PYTHON) -u scripts/refresh_prices.py
	@echo "\n══ 5/9  Fotografias em falta ou inválidas"
	$(PYTHON) -u scripts/capture_photos.py
	@echo "\n══ 6/9  Campanhas ainda expiradas e elegibilidade"
	$(PYTHON) -u scripts/expire_campaigns.py --apply
	@echo "\n══ 7/9  Imagens: recomprimir as pesadas e arrumar as órfãs"
	$(PYTHON) -u scripts/optimize_images.py --apply
	$(PYTHON) -u scripts/archive_unused_images.py --apply
	@echo "\n══ 8/9  Validar, compilar e testar"
	$(PYTHON) -u scripts/validate_data.py
	$(PYTHON) -u scripts/compile_data.py
	$(PYTHON) -u -m unittest discover -s tests
	$(NODE) --test tests/*.test.js
	@echo "\n══ 9/9  Ligações oficiais e concessionários"
	$(PYTHON) -u scripts/validate_data.py --check-links
	$(PYTHON) -u scripts/report_pending.py

# Nome antigo mantido para não quebrar rotinas locais; `update` é alvo canónico.
atualizar: update

# Aceitar fingerprints exige revisão humana explícita. O comando continua a
# validar tudo e falha se alguma fonte não puder ser lida.
update-accept:
	$(PYTHON) -u scripts/update_catalog.py --accept-source-changes

update-photos:
	$(PYTHON) -u scripts/capture_photos.py
	$(PYTHON) -u scripts/validate_data.py
	$(PYTHON) -u scripts/compile_data.py
	$(PYTHON) -u -m unittest discover -s tests
	$(NODE) --test tests/*.test.js

update-photos-all:
	$(PYTHON) -u scripts/capture_photos.py --all
	$(PYTHON) -u scripts/validate_data.py
	$(PYTHON) -u scripts/compile_data.py
	$(PYTHON) -u -m unittest discover -s tests
	$(NODE) --test tests/*.test.js

prune-images:
	$(PYTHON) -u scripts/archive_unused_images.py --apply
	$(PYTHON) -u scripts/validate_data.py
	$(PYTHON) -u scripts/compile_data.py
	$(PYTHON) -u -m unittest discover -s tests
	$(NODE) --test tests/*.test.js

# Determinístico e sem rede: só falha por regressão do código ou dos dados.
verificar:
	@$(RUFF) check .
	$(PYTHON) -u scripts/validate_data.py
	$(PYTHON) -u scripts/compile_data.py
	$(PYTHON) -u -m unittest discover -s tests
	$(NODE) --test tests/*.test.js
	$(PYTHON) -u scripts/report_pending.py

verify: verificar

lint:
	@$(RUFF) check .

validate:
	$(PYTHON) -u scripts/validate_data.py
	$(PYTHON) -u scripts/compile_data.py

test:
	$(PYTHON) -u -m unittest discover -s tests
	$(NODE) --test tests/*.test.js

links:
	$(PYTHON) -u scripts/validate_data.py --check-links

budgets:
	$(PYTHON) -u scripts/validate_data.py --check-budgets

freshness:
	$(PYTHON) -u scripts/validate_data.py --check-freshness

audit:
	@$(RUFF) check .
	$(PYTHON) -u scripts/validate_data.py --check-freshness
	$(PYTHON) -u scripts/compile_data.py
	$(PYTHON) -u -m unittest discover -s tests
	$(NODE) --test tests/*.test.js
	$(PYTHON) -u scripts/validate_data.py --check-links
	$(PYTHON) -u scripts/report_pending.py

sequential: update update-photos audit
