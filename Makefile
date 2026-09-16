.PHONY: install install-chatterbox test reproduce

install:
	pip install -e . && pip install -r requirements.lock

install-chatterbox:
	python3 -m venv .venv-chatterbox
	.venv-chatterbox/bin/pip install -r requirements-chatterbox.lock

test:
	pytest -q

reproduce:
	@echo "reproduce: placeholder, implemented in M16"
