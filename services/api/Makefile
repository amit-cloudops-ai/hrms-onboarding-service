.PHONY: build-ApiFunction

# Assemble only the files imported by the API Lambda. Do not package the
# repository root, frontend dependencies, tests, or Python cache directories.
build-ApiFunction:
	mkdir -p "$(ARTIFACTS_DIR)/services/identity" "$(ARTIFACTS_DIR)/services/workflow"
	cp handler.py "$(ARTIFACTS_DIR)/handler.py"
	cp services/identity/handler.py "$(ARTIFACTS_DIR)/services/identity/handler.py"
	cp services/workflow/handler.py "$(ARTIFACTS_DIR)/services/workflow/handler.py"
	cp services/workflow/callbacks.py "$(ARTIFACTS_DIR)/services/workflow/callbacks.py"
