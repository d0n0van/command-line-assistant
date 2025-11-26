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

# Test 2: Check CLI tool help
echo "Test 2: Testing 'cla --help'..."
if cla --help &> /dev/null; then
    echo "✓ cla --help works"
else
    echo "✗ cla --help failed"
    exit 1
fi

# Test 3: Check version
echo "Test 3: Testing 'cla --version'..."
if cla --version &> /dev/null; then
    echo "✓ cla --version works"
else
    echo "✗ cla --version failed"
    exit 1
fi

# Test 4: Check platform info
echo "Test 4: Testing 'cla --platform-info'..."
if cla --platform-info &> /dev/null; then
    echo "✓ cla --platform-info works"
else
    echo "✗ cla --platform-info failed"
    exit 1
fi

# Test 5: Check if config file exists
echo "Test 5: Checking config file..."
if [ -f /etc/xdg/command-line-assistant/config.toml ]; then
    echo "✓ config file found"
else
    echo "✗ config file not found"
    exit 1
fi

# Test 6: Check Python module import
echo "Test 6: Testing Python module import..."
if python3 -c "import command_line_assistant" &> /dev/null; then
    echo "✓ Python module can be imported"
else
    echo "✗ Python module import failed"
    exit 1
fi

echo ""
echo "=== All tests passed! ==="

