#!/bin/bash
set -e

echo "=== Testing Command Line Assistant Package ==="

# Test 1: Check if CLI tool is available
echo "Test 1: Checking if 'cla' command is available..."
if command -v cla &> /dev/null; then
    echo "✓ cla command found"
else
    echo "✗ cla command not found"
    exit 1
fi

# Test 2: Check if daemon binary is available
echo "Test 2: Checking if 'clad' command is available..."
if command -v clad &> /dev/null; then
    echo "✓ clad command found"
else
    echo "✗ clad command not found"
    exit 1
fi

# Test 3: Check CLI tool help
echo "Test 3: Testing 'cla --help'..."
if cla --help &> /dev/null; then
    echo "✓ cla --help works"
else
    echo "✗ cla --help failed"
    exit 1
fi

# Test 4: Check version
echo "Test 4: Testing 'cla --version'..."
if cla --version &> /dev/null; then
    echo "✓ cla --version works"
else
    echo "✗ cla --version failed"
    exit 1
fi

# Test 5: Check platform info
echo "Test 5: Testing 'cla --platform-info'..."
if cla --platform-info &> /dev/null; then
    echo "✓ cla --platform-info works"
else
    echo "✗ cla --platform-info failed"
    exit 1
fi

# Test 6: Check if systemd service file exists
echo "Test 6: Checking systemd service file..."
if [ -f /usr/lib/systemd/system/command-line-assistant.service ] || \
   [ -f /etc/systemd/system/command-line-assistant.service ]; then
    echo "✓ systemd service file found"
else
    echo "✗ systemd service file not found"
    exit 1
fi

# Test 7: Check if config file exists
echo "Test 7: Checking config file..."
if [ -f /etc/xdg/command-line-assistant/config.toml ]; then
    echo "✓ config file found"
else
    echo "✗ config file not found"
    exit 1
fi

# Test 8: Check Python module import
echo "Test 8: Testing Python module import..."
if python3 -c "import command_line_assistant" &> /dev/null; then
    echo "✓ Python module can be imported"
else
    echo "✗ Python module import failed"
    exit 1
fi

echo ""
echo "=== All tests passed! ==="

