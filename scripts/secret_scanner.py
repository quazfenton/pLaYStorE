#!/usr/bin/env python3
"""
Pre-commit hook for scanning secrets and sensitive data.

Detects and prevents committing:
- API keys and tokens
- Private keys
- Passwords and credentials
- AWS credentials
- Database connection strings
- JWT secrets
- OAuth client secrets

Installation:
    cp scripts/secret_scanner.py .git/hooks/pre-commit
    chmod +x .git/hooks/pre-commit

Or add to .git/hooks/pre-commit:
    python scripts/secret_scanner.py
"""

import re
import sys
import os
from pathlib import Path
from typing import List, Tuple

# Color codes for terminal output
class Colors:
    RED = '\033[91m'
    YELLOW = '\033[93m'
    GREEN = '\033[92m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


# Secret patterns to detect
SECRET_PATTERNS = [
    # AWS Credentials
    (r'AKIA[0-9A-Z]{16}', 'AWS Access Key ID', 'HIGH'),
    (r'(?i)aws[_\-]?secret[_\-]?access[_\-]?key\s*[=:]\s*["\']?[A-Za-z0-9/+=]{40}', 'AWS Secret Access Key', 'HIGH'),

    # GitHub Tokens
    (r'ghp_[A-Za-z0-9]{36}', 'GitHub Personal Access Token', 'HIGH'),
    (r'gho_[A-Za-z0-9]{36}', 'GitHub OAuth Token', 'HIGH'),
    (r'ghu_[A-Za-z0-9]{36}', 'GitHub User-to-Server Token', 'HIGH'),
    (r'ghs_[A-Za-z0-9]{36}', 'GitHub Server-to-Server Token', 'HIGH'),
    (r'ghr_[A-Za-z0-9]{36}', 'GitHub Refresh Token', 'HIGH'),

    # Generic API Keys
    (r'(?i)api[_\-]?key\s*[=:]\s*["\']?[A-Za-z0-9_\-]{20,}', 'API Key', 'MEDIUM'),
    (r'(?i)apikey\s*[=:]\s*["\']?[A-Za-z0-9_\-]{20,}', 'API Key', 'MEDIUM'),

    # Private Keys
    (r'-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----', 'Private Key', 'CRITICAL'),
    (r'(?i)private[_\-]?key\s*[=:]\s*["\']?[A-Za-z0-9_\-]{20,}', 'Private Key Reference', 'MEDIUM'),

    # Passwords
    (r'(?i)password\s*[=:]\s*["\'][^"\']{8,}["\']', 'Password', 'HIGH'),
    (r'(?i)passwd\s*[=:]\s*["\'][^"\']{8,}["\']', 'Password', 'HIGH'),
    (r'(?i)pwd\s*[=:]\s*["\'][^"\']{8,}["\']', 'Password', 'MEDIUM'),

    # Database URLs
    (r'(?i)(?:postgres|mysql|mongodb|redis)://[^:]+:[^@]+@', 'Database Connection String', 'HIGH'),
    (r'(?i)DATABASE_URL\s*[=:]\s*["\']?[^\s"\']+', 'Database URL', 'HIGH'),

    # JWT Secrets
    (r'(?i)jwt[_\-]?secret\s*[=:]\s*["\']?[A-Za-z0-9_\-]{16,}', 'JWT Secret', 'HIGH'),
    (r'(?i)jwt[_\-]?key\s*[=:]\s*["\']?[A-Za-z0-9_\-]{16,}', 'JWT Key', 'HIGH'),

    # OAuth Secrets
    (r'(?i)client[_\-]?secret\s*[=:]\s*["\']?[A-Za-z0-9_\-]{20,}', 'OAuth Client Secret', 'HIGH'),
    (r'(?i)oauth[_\-]?secret\s*[=:]\s*["\']?[A-Za-z0-9_\-]{20,}', 'OAuth Secret', 'HIGH'),

    # Stripe Keys
    (r'sk_live_[0-9a-zA-Z]{24}', 'Stripe Secret Key', 'HIGH'),
    (r'rk_live_[0-9a-zA-Z]{24}', 'Stripe Restricted Key', 'HIGH'),

    # Google API Keys
    (r'AIza[0-9A-Za-z\-_]{35}', 'Google API Key', 'HIGH'),

    # Slack Tokens
    (r'xox[baprs]-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24}', 'Slack Token', 'HIGH'),

    # SendGrid API Keys
    (r'SG\.[a-zA-Z0-9]{22}\.[a-zA-Z0-9]{43}', 'SendGrid API Key', 'HIGH'),

    # Twilio API Keys
    (r'SK[0-9a-fA-F]{32}', 'Twilio API Key', 'MEDIUM'),

    # Heroku API Keys
    (r'(?i)heroku[_\-]?api[_\-]?key\s*[=:]\s*["\']?[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}', 'Heroku API Key', 'HIGH'),

    # Generic Secrets
    (r'(?i)secret\s*[=:]\s*["\'][^"\']{16,}["\']', 'Generic Secret', 'MEDIUM'),
    (r'(?i)token\s*[=:]\s*["\'][^"\']{20,}["\']', 'Generic Token', 'MEDIUM'),

    # Master Keys
    (r'(?i)master[_\-]?key\s*[=:]\s*["\']?[A-Za-z0-9_\-]{32,}', 'Master Key', 'CRITICAL'),

    # Encryption Keys
    (r'(?i)encryption[_\-]?key\s*[=:]\s*["\']?[A-Za-z0-9_\-]{32,}', 'Encryption Key', 'CRITICAL'),
    (r'(?i)encrypt[_\-]?key\s*[=:]\s*["\']?[A-Za-z0-9_\-]{32,}', 'Encryption Key', 'CRITICAL'),
]

# Files to always skip
SKIP_FILES = [
    '.git/',
    'node_modules/',
    '__pycache__/',
    '.pyc',
    '.pyo',
    '.gitignore',
    'secret_scanner.py',
    '.secret_scanner_skip',
    'test_secret_scanner.py',
]

# File extensions to skip
SKIP_EXTENSIONS = [
    '.md',
    '.rst',
    '.txt',
    '.png',
    '.jpg',
    '.jpeg',
    '.gif',
    '.ico',
    '.pdf',
    '.bin',
    '.exe',
    '.dll',
    '.so',
    '.dylib',
]


def should_skip_file(filepath: str) -> bool:
    """Check if file should be skipped"""
    # Skip based on filename
    for skip in SKIP_FILES:
        if skip in filepath:
            return True

    # Skip based on extension
    for ext in SKIP_EXTENSIONS:
        if filepath.endswith(ext):
            return True

    # Skip .env.example files (these are templates)
    if filepath.endswith('.env.example') or filepath.endswith('.env.template'):
        return True

    # Skip test files for the scanner itself
    if 'test_secret_scanner' in filepath:
        return True

    return False


def get_staged_files() -> List[str]:
    """Get list of staged files from git"""
    try:
        import subprocess
        result = subprocess.run(
            ['git', 'diff', '--cached', '--name-only', '--diff-filter=ACM'],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip().split('\n') if result.stdout.strip() else []
    except subprocess.CalledProcessError:
        return []


def scan_file(filepath: str) -> List[Tuple[str, str, str, int]]:
    """
    Scan a file for secrets.

    Returns:
        List of tuples: (pattern_name, secret_value, severity, line_number)
    """
    findings = []

    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()

        for line_num, line in enumerate(lines, 1):
            # Skip comments in code files (but not in config files)
            if filepath.endswith(('.py', '.js', '.ts', '.go', '.rs')) and line.strip().startswith('#'):
                continue

            for pattern, name, severity in SECRET_PATTERNS:
                matches = re.findall(pattern, line)
                if matches:
                    for match in matches:
                        # Don't report if it's clearly a placeholder
                        if any(placeholder in match.lower() for placeholder in [
                            'your_', 'example', 'placeholder', 'xxx', 'changeme',
                            '<your', '${', '$(', '{{', 'todo', 'fixme'
                        ]):
                            continue

                        findings.append((name, match, severity, line_num))

    except Exception as e:
        print(f"{Colors.YELLOW}Warning: Could not scan {filepath}: {e}{Colors.RESET}")

    return findings


def scan_all_files(files: List[str]) -> bool:
    """
    Scan all files for secrets.

    Returns:
        True if secrets found (scan failed), False if clean
    """
    total_findings = []

    for filepath in files:
        if not filepath or should_skip_file(filepath):
            continue

        if not os.path.exists(filepath):
            continue

        findings = scan_file(filepath)
        for finding in findings:
            total_findings.append((filepath, *finding))

    # Report findings
    if total_findings:
        print(f"\n{Colors.RED}{Colors.BOLD}⛔ SECRET SCANNER: POTENTIAL SECRETS DETECTED ⛔{Colors.RESET}")
        print(f"{Colors.RED}Found {len(total_findings)} potential secret(s) in staged files:{Colors.RESET}\n")

        # Group by severity
        critical = [f for f in total_findings if f[3] == 'CRITICAL']
        high = [f for f in total_findings if f[3] == 'HIGH']
        medium = [f for f in total_findings if f[3] == 'MEDIUM']

        for filepath, name, secret, severity, line_num in critical:
            print(f"{Colors.RED}{Colors.BOLD}[CRITICAL]{Colors.RESET} {filepath}:{line_num}")
            print(f"  Type: {name}")
            print(f"  Value: {secret[:20]}...{secret[-5:] if len(secret) > 25 else ''}")
            print()

        for filepath, name, secret, severity, line_num in high:
            print(f"{Colors.RED}[HIGH]{Colors.RESET} {filepath}:{line_num}")
            print(f"  Type: {name}")
            print(f"  Value: {secret[:20]}...{secret[-5:] if len(secret) > 25 else ''}")
            print()

        for filepath, name, secret, severity, line_num in medium:
            print(f"{Colors.YELLOW}[MEDIUM]{Colors.RESET} {filepath}:{line_num}")
            print(f"  Type: {name}")
            print(f"  Value: {secret[:20]}...{secret[-5:] if len(secret) > 25 else ''}")
            print()

        print(f"\n{Colors.YELLOW}⚠️  COMMIT BLOCKED{Colors.RESET}")
        print(f"\n{Colors.BOLD}Recommended Actions:{Colors.RESET}")
        print("1. Remove the secrets from your code")
        print("2. Use environment variables instead:")
        print(f"   {Colors.BLUE}os.getenv('SECRET_KEY'){Colors.RESET}")
        print("3. Use a secrets manager (AWS Secrets Manager, HashiCorp Vault, etc.)")
        print("4. Add .env files to .gitignore")
        print(f"\n{Colors.BOLD}If this is a false positive:{Colors.RESET}")
        print(f"   Add the file to .gitignore or create a .secret_scanner_skip file")
        print(f"   Or use placeholder values like 'your_api_key_here'\n")

        return True  # Secrets found

    print(f"{Colors.GREEN}✓ SECRET SCANNER: No secrets detected in staged files{Colors.RESET}")
    return False  # Clean


def main():
    """Main entry point"""
    print(f"{Colors.BLUE}{Colors.BOLD}🔍 Running Secret Scanner...{Colors.RESET}\n")

    # Get staged files
    files = get_staged_files()

    if not files:
        print(f"{Colors.GREEN}✓ No staged files to scan{Colors.RESET}")
        sys.exit(0)

    print(f"Scanning {len(files)} staged file(s)...\n")

    # Scan files
    secrets_found = scan_all_files(files)

    # Exit with appropriate code
    sys.exit(1 if secrets_found else 0)


if __name__ == '__main__':
    main()
