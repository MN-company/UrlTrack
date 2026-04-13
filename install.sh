#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

BOLD='\033[1m'
RESET='\033[0m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'

INSTALL_DIR="$SCRIPT_DIR"

printf "${BOLD}UrlTrack installer${RESET}\n"

if [[ ! -f "$INSTALL_DIR/.env" ]]; then
    echo "Creating .env..."
    touch "$INSTALL_DIR/.env"

    echo ""
    echo -e "${BOLD}Required settings${RESET}"
    read -rp "  SECRET_KEY:   " SECRET_KEY
    read -rp "  SERVER_URL:   " SERVER_URL
    if [[ -n "$SECRET_KEY" ]]; then
        echo "SECRET_KEY=$SECRET_KEY" >> "$INSTALL_DIR/.env"
    fi
    if [[ -n "$SERVER_URL" ]]; then
        echo "SERVER_URL=$SERVER_URL" >> "$INSTALL_DIR/.env"
    fi

    echo ""
    echo -e "${BOLD}Gemini (optional — press Enter to skip)${RESET}"
    read -rp "  GEMINI_API_KEY: " GEMINI_API_KEY
    read -rp "  GEMINI_MODEL:   " GEMINI_MODEL
    if [[ -n "$GEMINI_API_KEY" ]]; then
        echo "GEMINI_API_KEY=$GEMINI_API_KEY" >> "$INSTALL_DIR/.env"
    fi
    if [[ -n "$GEMINI_MODEL" ]]; then
        echo "GEMINI_MODEL=$GEMINI_MODEL" >> "$INSTALL_DIR/.env"
    fi

    # Cloudflare Turnstile (captcha gate)
    echo ""
    echo -e "${BOLD}Cloudflare Turnstile captcha (optional — press Enter to skip)${RESET}"
    echo "  Get keys at: https://dash.cloudflare.com → Turnstile"
    read -rp "  TURNSTILE_SITE_KEY:   " TURNSTILE_SITE
    read -rp "  TURNSTILE_SECRET_KEY: " TURNSTILE_SECRET
    if [[ -n "$TURNSTILE_SITE" ]]; then
        echo "TURNSTILE_SITE_KEY=$TURNSTILE_SITE" >> "$INSTALL_DIR/.env"
    fi
    if [[ -n "$TURNSTILE_SECRET" ]]; then
        echo "TURNSTILE_SECRET_KEY=$TURNSTILE_SECRET" >> "$INSTALL_DIR/.env"
    fi

    echo ""
    echo -e "${GREEN}Done.${RESET}"
    echo "  .env created at $INSTALL_DIR/.env"
fi
