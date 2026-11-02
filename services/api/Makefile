.PHONY: build-ApiFunction

# Build a deliberately small Lambda artifact. The API imports only the identity
# handler and workflow handler/callback modules from the shared services tree.
build-ApiFunction:
	mkdir -p "$(ARTIFACTS_DIR)/services/identity" "$(ARTIFACTS_DIR)/services/workflow"
	cp handler.py "$(ARTIFACTS_DIR)/handler.py"
	cp ../identity/handler.py "$(ARTIFACTS_DIR)/services/identity/handler.py"
	cp ../workflow/handler.py "$(ARTIFACTS_DIR)/services/workflow/handler.py"
	cp ../workflow/callbacks.py "$(ARTIFACTS_DIR)/services/workflow/callbacks.py"
