#!/bin/bash
# SpiderFoot Darkweb Scanner - Tor Enabled
# This script starts SpiderFoot with Tor proxy pre-configured for darkweb scanning

echo "========================================"
echo "SpiderFoot Darkweb Scanner (Tor Enabled)"
echo "========================================"

# Check if Tor is installed
if ! command -v tor &> /dev/null; then
    echo "Error: Tor is not installed!"
    echo "Please install Tor first: sudo apt-get install tor"
    exit 1
fi

# Check if Tor is running
if ! pgrep -x "tor" > /dev/null; then
    echo "Starting Tor service..."
    sudo service tor start
    sleep 5
fi

# Verify Tor is running on port 9050
if ! nc -z localhost 9050 2>/dev/null; then
    echo "Error: Tor is not running on port 9050"
    echo "Please check your Tor configuration"
    exit 1
fi

echo "✓ Tor is running on port 9050"

# Set Tor proxy environment variables
export SOCKS_PROXY="socks5://127.0.0.1:9050"

# Start SpiderFoot with Tor proxy configuration
echo ""
echo "Starting SpiderFoot with Tor proxy enabled..."
echo "Web UI will be available at: http://0.0.0.0:5001"
echo ""
echo "Default Tor proxy settings:"
echo "  - SOCKS Type: 5 (SOCKS5)"
echo "  - SOCKS Server: 127.0.0.1"
echo "  - SOCKS Port: 9050"
echo ""
echo "Recommended modules for darkweb scanning:"
echo "  - ahmia (Tor search engine)"
echo "  - torexits (Check for Tor exit nodes)"
echo "  - torch (Tor search engine)"
echo "  - onionsearchengine"
echo ""

python3 sf.py -l 0.0.0.0:5001 \
    -o _socks1type=5 \
    -o _socks2addr=127.0.0.1 \
    -o _socks3port=9050 \
    -o _socks4user= \
    -o _socks5pwd=