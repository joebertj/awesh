CC = gcc
CFLAGS = -Wall -Wextra -std=c99
LIBS = -lreadline

TARGET = awesh
SECURITY_AGENT = awesh_sec
SANDBOX = awesh_sandbox
SOURCE = awesh.c
SECURITY_AGENT_SOURCE = security_agent.c
SANDBOX_SOURCE = awesh_sandbox.c
BACKEND_PKG = ../awesh_backend

all: $(TARGET) $(SECURITY_AGENT) $(SANDBOX) backend

$(TARGET): $(SOURCE)
	$(CC) $(CFLAGS) -o $(TARGET) $(SOURCE) $(LIBS)

$(SECURITY_AGENT): $(SECURITY_AGENT_SOURCE)
	$(CC) $(CFLAGS) -o $(SECURITY_AGENT) $(SECURITY_AGENT_SOURCE)

$(SANDBOX): $(SANDBOX_SOURCE)
	$(CC) $(CFLAGS) -o $(SANDBOX) $(SANDBOX_SOURCE)

backend:
	@echo "Backend package ready at $(BACKEND_PKG)"

clean:
	rm -f $(TARGET) $(SECURITY_AGENT) $(SANDBOX)

install: $(TARGET) backend
	@echo "Installing awesh to ~/.local/bin..."
	mkdir -p ~/.local/bin
	cp $(TARGET) ~/.local/bin/
	@echo "Installing Python backend package..."
	cd .. && pip install -e .
	@echo "✅ awesh installation complete!"
	@echo "Run 'awesh' from anywhere to start the shell"

install-system: $(TARGET) backend
	@echo "Installing awesh system-wide..."
	sudo cp $(TARGET) /usr/local/bin/
	sudo chmod +x /usr/local/bin/$(TARGET)
	cd .. && sudo pip install -e .
	@echo "✅ awesh installed system-wide!"

uninstall:
	@echo "Uninstalling awesh..."
	rm -f ~/.local/bin/$(TARGET)
	pip uninstall -y awesh-backend
	@echo "✅ awesh uninstalled"

.PHONY: all clean install install-system uninstall backend
