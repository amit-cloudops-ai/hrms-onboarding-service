.PHONY: build-ApiFunction

# SAM copies this CodeUri into the artifact directory before invoking make.
# Shared runtime modules are vendored under services/api/services so the
# Lambda package is self-contained and never reaches outside CodeUri.
build-ApiFunction:
	mkdir -p "$(ARTIFACTS_DIR)/services/identity" "$(ARTIFACTS_DIR)/services/workflow"
