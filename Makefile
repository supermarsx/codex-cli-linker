.PHONY: help configure check test run ci clean
.DEFAULT_GOAL := help

BUILD_DIR ?= build
CMAKE ?= cmake

# Pass run-time options to CMake cache via -D...
RUN_DEFS :=
ifdef AUTO
  RUN_DEFS += -DCODEX_AUTO=ON
endif
ifdef FULL_AUTO
  RUN_DEFS += -DCODEX_FULL_AUTO=ON
endif
ifdef JSON
  RUN_DEFS += -DCODEX_JSON=ON
endif
ifdef YAML
  RUN_DEFS += -DCODEX_YAML=ON
endif
ifdef DRY_RUN
  RUN_DEFS += -DCODEX_DRY_RUN=ON
endif
ifdef VERBOSE
  RUN_DEFS += -DCODEX_VERBOSE=ON
endif
ifdef BASE_URL
  RUN_DEFS += -DCODEX_BASE_URL=$(BASE_URL)
endif
ifdef PROVIDER
  RUN_DEFS += -DCODEX_PROVIDER=$(PROVIDER)
endif
ifdef PROFILE
  RUN_DEFS += -DCODEX_PROFILE=$(PROFILE)
endif
ifdef MODEL
  RUN_DEFS += -DCODEX_MODEL=$(MODEL)
endif
ifdef MODEL_INDEX
  RUN_DEFS += -DCODEX_MODEL_INDEX=$(MODEL_INDEX)
endif

help:
	@echo "Targets: configure check test run ci clean"
	@echo "Flags for run: AUTO=1 FULL_AUTO=1 JSON=1 YAML=1 DRY_RUN=1 VERBOSE=1"
	@echo "Values: BASE_URL=... PROVIDER=... PROFILE=... MODEL=... MODEL_INDEX=..."

configure:
	$(CMAKE) -S . -B $(BUILD_DIR)

check: configure
	$(CMAKE) --build $(BUILD_DIR) --target check

test: configure
	$(CMAKE) --build $(BUILD_DIR) --target test

run:
	$(CMAKE) -S . -B $(BUILD_DIR) $(RUN_DEFS)
	$(CMAKE) --build $(BUILD_DIR) --target run

ci: check test

clean:
	$(CMAKE) -E rm -rf $(BUILD_DIR)
