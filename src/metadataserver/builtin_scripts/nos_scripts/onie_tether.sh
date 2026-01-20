#!/bin/sh
# MAAS ONIE Tether Script
# This script runs on the switch during ONIE installation
# It polls MAAS for an assigned NOS installer and installs it when available
#
# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

API_URL="$api_url"
MAC_ADDRESS="$mac_address"
POLL_INTERVAL=$poll_interval
INSTALLER_PATH="/tmp/nos-installer.bin"
LOG_FILE="/tmp/maas-onie-install.log"

log() {
    echo "$$(date): $$1" | tee -a $$LOG_FILE
}

log "MAAS ONIE Tether Script started"
log "MAC Address: $$MAC_ADDRESS"
log "API URL: $$API_URL"
log "NOS installer path: $$API_URL$v3_api_prefix/nos-installer?mac=$$MAC_ADDRESS"

# Main installation loop
while true; do
    log "Checking for assigned NOS installer..."
    
    # Clean up any previous download
    rm -f $$INSTALLER_PATH
    
    # Request installer from MAAS (BusyBox wget compatible)
    # Pass MAC address as query parameter since BusyBox wget doesn't support POST data
    wget -q -O $$INSTALLER_PATH "$$API_URL$v3_api_prefix/nos-installer?mac=$$MAC_ADDRESS" 2>&1 | tee -a $$LOG_FILE
    WGET_EXIT=$$?
    
    log "wget exit code: $$WGET_EXIT"
    
    # Check if file was downloaded and has content
    if [ -f "$$INSTALLER_PATH" ] && [ -s "$$INSTALLER_PATH" ]; then
        log "NOS installer downloaded successfully"
        log "Installer size: $$(wc -c < $$INSTALLER_PATH) bytes"
        
        # Check if it's an actual binary or an error message
        # Error messages are typically plain text and small
        FILE_SIZE=$$(wc -c < $$INSTALLER_PATH)
        if [ "$$FILE_SIZE" -lt 1000 ]; then
            log "Downloaded file is too small to be a valid installer"
            log "Content: $$(cat $$INSTALLER_PATH)"
            log "No installer assigned yet, will retry in $$POLL_INTERVAL seconds..."
        else
            log "Installing NOS..."
            
            # Make installer executable
            chmod +x $$INSTALLER_PATH
            
            # Execute the installer and capture output
            if $$INSTALLER_PATH 2>&1 | tee -a $$LOG_FILE; then
                log "NOS installation completed successfully"
                log "Installation complete. Rebooting switch..."
                sleep 5
                reboot
                exit 0
            else
                log "ERROR: NOS installation failed"
                exit 1
            fi
        fi
    else
        log "No installer available or file is empty"
        log "Will retry in $$POLL_INTERVAL seconds..."
    fi
    
    # Clean up
    rm -f $$INSTALLER_PATH
    
    # Wait before next poll
    sleep $$POLL_INTERVAL
done
