.PHONY: build-ApiFunction

# SAM builds the API from the repository root so its shared runtime modules
# are packaged at the same import paths used by services/api/handler.py.
build-ApiFunction:
	mkdir -p "$(ARTIFACTS_DIR)/services/api"
	mkdir -p "$(ARTIFACTS_DIR)/services/identity"
	mkdir -p "$(ARTIFACTS_DIR)/services/workflow"
	touch "$(ARTIFACTS_DIR)/services/__init__.py"
	touch "$(ARTIFACTS_DIR)/services/api/__init__.py"
	touch "$(ARTIFACTS_DIR)/services/identity/__init__.py"
	touch "$(ARTIFACTS_DIR)/services/workflow/__init__.py"
	cp services/api/handler.py "$(ARTIFACTS_DIR)/services/api/handler.py"
	cp services/identity/handler.py "$(ARTIFACTS_DIR)/services/identity/handler.py"
	cp services/workflow/handler.py "$(ARTIFACTS_DIR)/services/workflow/handler.py"
	cp services/workflow/callbacks.py "$(ARTIFACTS_DIR)/services/workflow/callbacks.py"
