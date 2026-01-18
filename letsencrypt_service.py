#!/usr/bin/env python3
"""
Automated SSL Certificate Renewal with Certbot Manual HTTP Challenge
Requires: certbot, certbot-dns-* plugins (optional)
Run as: sudo python3 certbot_renewal.py
"""

import subprocess
import os
import sys
from pathlib import Path
from deploy_qiniu import upload_acme_challenge as qiniu_upload_acme_challenge
from deploy_qiniu import delete_acme_challenge as qiniu_delete_acme_challenge

# Configuration
DOMAIN = os.getenv("CERT_DOMAIN")   # Change to your domain
EMAIL = os.getenv("CERT_EMAIL")  # Change to your email
WEBROOT_PATH = "/tmp/acme_challenge/.well-known/acme-challenge"  # HTTP challenge path
WEB_CONF_FILE = "qiniu_config.toml"
CERTBOT_DIR_ROOT="./.cache"

# WORKING_DIRS
CERTBOT_DIR_LOG=os.path.join(CERTBOT_DIR_ROOT,"log")
CERTBOT_DIR_WORK=os.path.join(CERTBOT_DIR_ROOT,"work")
CERTBOT_DIR_CONFIG=os.path.join(CERTBOT_DIR_ROOT,"config")
CERTBOT_DIR_HOOKS = os.path.join(CERTBOT_DIR_ROOT, "hooks")


def deploy_challenge(domain, token, validation):
    """
    Deploy the HTTP challenge to your web server.
    Modify this function to call your deployment method.
    
    Args:
        domain: The domain being validated
        token: The challenge token
        validation: The validation string to serve
    """
    print(f"\n{'='*60}")
    print(f"DEPLOY HTTP CHALLENGE FOR: {domain}")
    print(f"{'='*60}")
    print(f"Token: {token}")
    print(f"Validation: {validation}")
    print(f"\nYou need to make this URL accessible:")
    print(f"http://{domain}/.well-known/acme-challenge/{token}")
    print(f"\nIt should return: {validation}")
    print(f"{'='*60}\n")
    
    # Option 1: Write to local webroot (if this server hosts the domain)
    try:
        challenge_dir = Path(WEBROOT_PATH)
        challenge_dir.mkdir(parents=True, exist_ok=True)
        challenge_file = challenge_dir / token
        challenge_file.write_text(validation)
        print(f"✅ Challenge file created at: {challenge_file}")
    except Exception as e:
        print(f"⚠ Could not write to local webroot: {e}")
    
    # Option 2: Call your custom deployment function/API
    # Example: deploy_to_remote_server(domain, token, validation)
    # Example: update_cdn_configuration(domain, token, validation)
    ret = qiniu_upload_acme_challenge(token, validation)
    if not ret:
        print(f"⛔️ Fail to deploy challenge file")

def cleanup_challenge(domain, token):
    """
    Clean up the HTTP challenge after validation.
    
    Args:
        domain: The domain that was validated
        token: The challenge token to remove
    """
    print(f"\n{'='*60}")
    print(f"CLEANUP CHALLENGE FOR: {domain}")
    print(f"{'='*60}")
    
    # Remove local challenge file if it exists
    try:
        challenge_file = Path(WEBROOT_PATH) / token
        if challenge_file.exists():
            challenge_file.unlink()
            print(f"✓ Removed challenge file: {challenge_file}")
    except Exception as e:
        print(f"⚠ Could not remove challenge file: {e}")
    
    qiniu_delete_acme_challenge(token)


def run_certbot_manual(staging=True):
    """
    Run certbot in manual mode with hooks for challenge deployment.
    """
    mode = "STAGING" if staging else "PRODUCTION"
    print(f"Starting Certbot certificate request in {mode} mode...\n")
    
    if staging:
        print("⚠ STAGING MODE: Certificate will NOT be trusted by browsers")
        print("  Use this for testing. Set STAGING=False for production.\n")
    else:
        print("❇️ PRODUCTION MODE: Certificate will be valid.")
    
    # Create hook scripts
    hook_dir = Path(CERTBOT_DIR_HOOKS)
    hook_dir.mkdir(exist_ok=True)
    
    # Auth hook script
    auth_hook = hook_dir / "auth_hook.sh"
    auth_hook.write_text(f"""#!/bin/bash
python3 -c "
import sys
sys.path.insert(0, '{os.getcwd()}')
from {Path(__file__).stem} import deploy_challenge
deploy_challenge('$CERTBOT_DOMAIN', '$CERTBOT_TOKEN', '$CERTBOT_VALIDATION')
"
""")
    auth_hook.chmod(0o755)
    
    # Cleanup hook script
    cleanup_hook = hook_dir / "cleanup_hook.sh"
    cleanup_hook.write_text(f"""#!/bin/bash
python3 -c "
import sys
sys.path.insert(0, '{os.getcwd()}')
from {Path(__file__).stem} import cleanup_challenge
cleanup_challenge('$CERTBOT_DOMAIN', '$CERTBOT_TOKEN')
"
""")
    cleanup_hook.chmod(0o755)
    
    # Build certbot command
    cmd = [
        "certbot", "certonly",
        "--manual",
        "--preferred-challenges", "http",
        "--manual-auth-hook", str(auth_hook),
        "--manual-cleanup-hook", str(cleanup_hook),
        "-d", DOMAIN,
        # "--email", EMAIL,
        "--agree-tos",
        "--non-interactive",
        "--logs-dir", CERTBOT_DIR_LOG,
        "--config-dir", CERTBOT_DIR_CONFIG,
        "--work-dir", CERTBOT_DIR_WORK,
        # "--manual-public-ip-logging-ok"
    ]
    
    # Add staging flag if enabled
    if staging:
        cmd.append("--staging")
    
    print(f"[INFO] Running certbot cmd: {cmd}")
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error running certbot: {e}")
        print(f"STDOUT: {e.stdout}")
        print(f"STDERR: {e.stderr}")
        return False

def prepare_dir():
    dir_list = [
        WEBROOT_PATH,
        CERTBOT_DIR_LOG,
        CERTBOT_DIR_WORK,
        CERTBOT_DIR_CONFIG,
        CERTBOT_DIR_HOOKS,
    ]
    for p in dir_list:
        os.makedirs(p, exist_ok=True)

def main():
    """
    Main execution flow.
    """
    STAGING = True
    env_mode = os.getenv("CERT_IN_PROD")
    if env_mode is None or env_mode != "1":
        STAGING = True
    else:
        STAGING = False
    mode = "STAGING" if STAGING else "PRODUCTION"

    if DOMAIN is None or DOMAIN == "":
        print("Domain should not be empty!")
        return
    
    print(f"\n{'='*60}")
    print("SSL CERTIFICATE RENEWAL SCRIPT")
    print(f"Mode: {mode}")
    print(f"Domain: {DOMAIN}")
    print(f"Email: {EMAIL}")
    print(f"{'='*60}\n")

    if STAGING:
        print("🧪 RUNNING IN STAGING MODE")
        print("   - Certificates will be issued by Let's Encrypt Staging")
        print("   - NOT trusted by browsers (for testing only)")
        print("   - No rate limits")
        print("   - Set environ variable CERT_IN_PROD=1 for production certificates\n")
    else:
        print("❇️ RUNNING IN PRODUCTION MODE")
    # Prepare directories
    prepare_dir()

    # Run certbot
    print("\nStarting certificate renewal process...\n")
    success = run_certbot_manual(STAGING)
    
    if success:
        print("\n✅ Certificate successfully obtained!")
        if STAGING:
            print("⚠ Remember: This is a STAGING certificate (not trusted)")
        # save_certificates()
        print("\n✅ Process completed successfully!")
    else:
        print("\n❌ Certificate renewal failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()