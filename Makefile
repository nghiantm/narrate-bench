.PHONY: install test reproduce

install:
	pip install -e . && pip install -r requirements.lock

test:
	pytest -q

reproduce:
	@echo "reproduce: placeholder, implemented in M16"
