.PHONY: update update-accept update-photos update-photos-all prune-images validate links test audit sequential serve

update:
	python3 scripts/update_catalog.py

update-accept:
	python3 scripts/update_catalog.py --accept-source-changes

update-photos:
	python3 scripts/capture_photos.py
	$(MAKE) validate
	$(MAKE) test

update-photos-all:
	python3 scripts/capture_photos.py --all
	$(MAKE) validate
	$(MAKE) test

prune-images:
	python3 scripts/archive_unused_images.py --apply
	$(MAKE) validate
	$(MAKE) test

validate:
	python3 scripts/validate_data.py
	python3 scripts/compile_data.py

links:
	python3 scripts/validate_data.py --check-links

test:
	python3 -m unittest discover -s tests
	node --test tests/*.test.js

audit:
	$(MAKE) validate
	$(MAKE) test
	$(MAKE) links

sequential:
	@echo "[1/3] Verificar fontes conhecidas e atualizar o catálogo"
	$(MAKE) update
	@echo "[2/3] Capturar fotografias em falta"
	$(MAKE) update-photos
	@echo "[3/3] Executar auditoria final"
	$(MAKE) audit
	@echo "Pipeline sequencial concluído."

serve:
	python3 scripts/serve.py
