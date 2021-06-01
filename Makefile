.venv:
	python3.9 -m venv .venv

.PHONY: install_requirements
install_requirements:
	pip3 install -r requirements


.PHONY: run
run:
	python3 main.py


