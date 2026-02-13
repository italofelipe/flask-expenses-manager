#!/usr/bin/env bash
set -euo pipefail

# Baseline host firewall hardening for Auraxis EC2 instances.
# This is designed to be safe with SSM (no SSH required).
#
# Rules:
# - Default deny incoming
# - Allow outgoing
# - Allow HTTP/HTTPS inbound
#
# Notes:
# - Docker has known interactions with UFW/iptables. This script only sets a
#   minimal inbound policy; if you need to firewall container-to-container or
#   Docker-published ports, handle it explicitly.

export DEBIAN_FRONTEND=noninteractive

echo "[ufw] Installing ufw..."
if command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update -y
  sudo apt-get install -y ufw
else
  echo "[ufw] ERROR: apt-get not found (expected Ubuntu/Debian)."
  exit 1
fi

echo "[ufw] Resetting and configuring defaults..."
sudo ufw --force reset
sudo ufw default deny incoming
sudo ufw default allow outgoing

echo "[ufw] Allowing web ports..."
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

echo "[ufw] Allowing loopback..."
sudo ufw allow in on lo

echo "[ufw] Enabling firewall..."
sudo ufw --force enable

echo "[ufw] Status:"
sudo ufw status verbose

