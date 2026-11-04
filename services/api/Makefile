.PHONY: build-ApiFunction

# SAM runs this Makefile from services/api (the CodeUri). Assemble only the
# runtime modules imported by handler.py. Never package the repository root.
build-ApiFunction:
	mkdir -p "$(ARTIFACTS_DIR)/services/identity" "$(ARTIFACTS_DIR)/services/workflow"
	cp handler.py "$(ARTIFACTS_DIR)/handler.py"
	cp ../identity/handler.py "$(ARTIFACTS_DIR)/services/identity/handler.py"
	cp ../workflow/handler.py "$(ARTIFACTS_DIR)/services/workflow/handler.py"
	cp ../workflow/callbacks.py "$(ARTIFACTS_DIR)/services/workflow/callbacks.py"
