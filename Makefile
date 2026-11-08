CONFIG ?= training/config.yaml
SUBSET ?=

.PHONY: train
train:
	SUBSET=$(SUBSET) python3 training/train.py $(CONFIG)
