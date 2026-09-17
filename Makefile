.PHONY: install install-chatterbox install-whisperx test reproduce

install:
	pip install -e . && pip install -r requirements.lock

install-chatterbox:
	python3 -m venv .venv-chatterbox
	.venv-chatterbox/bin/pip install -r requirements-chatterbox.lock

install-whisperx:
	python3 -m venv .venv-whisperx
	.venv-whisperx/bin/pip install -r requirements-whisperx.lock

test:
	pytest -q

reproduce:
	@echo "reproduce: placeholder, implemented in M16"
