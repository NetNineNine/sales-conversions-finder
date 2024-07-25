#set default
.ONESHELL:
.DEFAULT_GOAL := dev

SHELL := /bin/bash
DOCKER = $(shell docker info >/dev/null 2>&1 && echo "docker" || echo "sudo docker")
REGISTRY = netninenine.co.za
IMAGE = sales-conversions-finder
PYTHON = venv/bin/python3
PIP = venv/bin/pip3
TAG_NAME ?= $(shell git rev-parse --short HEAD)

.PHONY: build venv dev run clean

venv: requirements.txt
	@echo "==> Installing requirements..."
	python3 -m venv venv
	. venv/bin/activate
	$(PIP) install -r requirements.txt
	touch venv/bin/activate

dev: venv
	@echo "==> Running app in dev mode with hot-reload enabled..."
	@echo "==> Activating virtual environment..."
	. venv/bin/activate
	uvicorn app:app --port 8086 --reload

run: build
	@echo "==> Running app using docker..."
	@echo "==> Activating virtual environment..."
	@$(DOCKER) rm -f ${IMAGE} || true
	@$(DOCKER) run --rm -d --env-file .env --name sales-conversions-finder -it -v .:/app -p 8086:8086 $(REGISTRY)/$(IMAGE):latest

clean:
	@echo "==> Cleaning working directory..."
	rm -rf venv
	rm -rf __pycache__

build:
	@echo "==> Building $(IMAGE)"
	@$(DOCKER) build -t $(REGISTRY)/$(IMAGE):$(TAG_NAME) .
	@$(DOCKER) tag $(REGISTRY)/$(IMAGE):$(TAG_NAME) $(REGISTRY)/$(IMAGE):latest
