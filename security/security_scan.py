#!/usr/bin/env python3
"""
FlowSlide Security Scanner
Comprehensive security analysis and vulnerability detection
"""

import os
import sys
import json
import subprocess
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any


class SecurityScanner:
    """Comprehensive security scanner for FlowSlide"""

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.results_dir = Path("security_results")
        self.results_dir.mkdir(exist_ok=True)
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    def run_all_scans(self) -> Dict[str, Any]:
        """Run all security scans"""
        print("🔒 Starting FlowSlide Security Audit")
        print("=" * 50)

        results = {
            "timestamp": self.timestamp,
            "project_root": str(self.project_root),
            "scans": {}
        }

        # Run individual scans
        scans = [
            ("dependency_scan", self.scan_dependencies),
            ("code_scan", self.scan_code_vulnerabilities),
            ("secrets_scan", self.scan_secrets),
            ("docker_scan", self.scan_docker_security),
            ("config_scan", self.scan_configuration),
            ("api_security", self.scan_api_security),
            ("auth_security", self.scan_authentication),
        ]

        for scan_name, scan_func in scans:
            print(f"\n🔍 Running {scan_name.replace('_', ' ').title()}")
            try:
                scan_result = scan_func()
                results["scans"][scan_name] = scan_result

                if scan_result.get("issues"):
                    print(f"⚠️ Found {len(scan_result['issues'])} issues")
                else:
                    print("✅ No issues found")

            except Exception as e:
                print(f"❌ Scan failed: {e}")
                results["scans"][scan_name] = {"error": str(e)}

        # Save results
        self.save_results(results)
        self.generate_report(results)

        return results

    def scan_dependencies(self) -> Dict[str, Any]:
        """Scan for vulnerable dependencies"""
        issues = []

        # Check if safety is installed
        try:
            subprocess.run(["safety", "--version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            return {"error": "Safety not installed. Install with: pip install safety"}

        # Run safety check
        try:
            result = subprocess.run(
                ["safety", "check", "--json"],
                capture_output=True,
                text=True,
                cwd=self.project_root
            )

            if result.stdout:
                safety_data = json.loads(result.stdout)
                for vuln in safety_data:
                    issues.append({
                        "type": "vulnerable_dependency",
                        "severity": "high",
                        "package": vuln.get("package_name"),
                        "version": vuln.get("installed_version"),
                        "vulnerability": vuln.get("vulnerability_id"),
                        "description": vuln.get("advisory"),
                        "fix": f"Update to version {vuln.get('safe_versions', 'latest')}"
                    })

        except Exception as e:
            return {"error": f"Safety scan failed: {e}"}

        # Check for outdated packages
        try:
            result = subprocess.run(
                ["pip", "list", "--outdated", "--format=json"],
                capture_output=True,
                text=True
            )

            if result.stdout:
                outdated = json.loads(result.stdout)
                for pkg in outdated:
                    issues.append({
                        "type": "outdated_dependency",
                        "severity": "medium",
                        "package": pkg["name"],
                        "current_version": pkg["version"],
                        "latest_version": pkg["latest_version"],
                        "description": f"Package {pkg['name']} is outdated",
                        "fix": f"Update to version {pkg['latest_version']}"
                    })

        except Exception as e:
            print(f"Warning: Could not check outdated packages: {e}")

        return {"issues": issues, "total_issues": len(issues)}

    def scan_code_vulnerabilities(self) -> Dict[str, Any]:
        """Scan code for security vulnerabilities using bandit"""
        issues = []

        # Check if bandit is installed
        try:
            subprocess.run(["bandit", "--version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            return {"error": "Bandit not installed. Install with: pip install bandit"}

        # Run bandit scan
        try:
            result = subprocess.run([
                "bandit", "-r", "src/", "-f", "json", "-o", "-"
            ], capture_output=True, text=True, cwd=self.project_root)

            if result.stdout:
                bandit_data = json.loads(result.stdout)

                for issue in bandit_data.get("results", []):
                    issues.append({
                        "type": "code_vulnerability",
                        "severity": issue.get("issue_severity", "unknown").lower(),
                        "file": issue.get("filename"),
                        "line": issue.get("line_number"),
                        "test_id": issue.get("test_id"),
                        "description": issue.get("issue_text"),
                        "confidence": issue.get("issue_confidence"),
                        "code": issue.get("code"),
                        "fix": "Review and fix the security issue"
                    })

        except Exception as e:
            return {"error": f"Bandit scan failed: {e}"}

        return {"issues": issues, "total_issues": len(issues)}

    def scan_secrets(self) -> Dict[str, Any]:
        """Scan for exposed secrets and credentials"""
        issues = []

        # Patterns for common secrets
        secret_patterns = [
            (r"password\s*=\s*['\"][^'\"]+['\"]", "hardcoded_password"),
            (r"api_key\s*=\s*['\"][^'\"]+['\"]", "hardcoded_api_key"),
            (r"secret_key\s*=\s*['\"][^'\"]+['\"]", "hardcoded_secret_key"),
            (r"token\s*=\s*['\"][^'\"]+['\"]", "hardcoded_token"),
            (r"sk-[a-zA-Z0-9]{48}", "openai_api_key"),
            (r"xoxb-[0-9]{11}-[0-9]{11}-[a-zA-Z0-9]{24}", "slack_token"),
            (r"ghp_[a-zA-Z0-9]{36}", "github_token"),
        ]

        # Scan Python files
        for py_file in self.project_root.rglob("*.py"):
            if "venv" in str(py_file) or "__pycache__" in str(py_file):
                continue

            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                for line_num, line in enumerate(content.split('\n'), 1):
                    for pattern, secret_type in secret_patterns:
                        import re
                        if re.search(pattern, line, re.IGNORECASE):
                            issues.append({
                                "type": "exposed_secret",
                                "severity": "critical",
                                "file": str(py_file),
                                "line": line_num,
                                "secret_type": secret_type,
                                "description": f"Potential {secret_type} found in code",
                                "fix": "Move secret to environment variable or secure vault"
                            })

            except Exception as e:
                print(f"Warning: Could not scan {py_file}: {e}")

        # Check for .env files with secrets
        for env_file in self.project_root.rglob(".env*"):
            if env_file.name == ".env.example":
                continue

            issues.append({
                "type": "env_file_exposure",
                "severity": "high",
                "file": str(env_file),
                "description": "Environment file may contain secrets",
                "fix": "Ensure .env files are in .gitignore and not committed"
            })

        return {"issues": issues, "total_issues": len(issues)}

    def scan_docker_security(self) -> Dict[str, Any]:
        """Scan Docker configuration for security issues"""
        issues = []

        # Check Dockerfile
        dockerfile = self.project_root / "Dockerfile"
        if dockerfile.exists():
            try:
                with open(dockerfile, 'r') as f:
                    content = f.read()

                # Check for security issues
                if "USER root" in content:
                    issues.append({
                        "type": "docker_security",
                        "severity": "high",
                        "file": "Dockerfile",
                        "description": "Running as root user in Docker",
                        "fix": "Create and use a non-root user"
                    })

                if "--privileged" in content:
                    issues.append({
                        "type": "docker_security",
                        "severity": "critical",
                        "file": "Dockerfile",
                        "description": "Privileged mode detected",
                        "fix": "Remove --privileged flag unless absolutely necessary"
                    })

                if "ADD http" in content or "ADD https" in content:
                    issues.append({
                        "type": "docker_security",
                        "severity": "medium",
                        "file": "Dockerfile",
                        "description": "Using ADD with URLs",
                        "fix": "Use COPY instead of ADD for local files"
                    })

            except Exception as e:
                print(f"Warning: Could not scan Dockerfile: {e}")

        # Check docker-compose files
        for compose_file in self.project_root.glob("docker-compose*.yml"):
            try:
                with open(compose_file, 'r') as f:
                    content = f.read()

                if "privileged: true" in content:
                    issues.append({
                        "type": "docker_security",
                        "severity": "critical",
                        "file": str(compose_file),
                        "description": "Privileged container detected",
                        "fix": "Remove privileged: true unless absolutely necessary"
                    })

                if "network_mode: host" in content:
                    issues.append({
                        "type": "docker_security",
                        "severity": "high",
                        "file": str(compose_file),
                        "description": "Host network mode detected",
                        "fix": "Use bridge networking instead of host mode"
                    })

            except Exception as e:
                print(f"Warning: Could not scan {compose_file}: {e}")

        return {"issues": issues, "total_issues": len(issues)}

    def scan_configuration(self) -> Dict[str, Any]:
        """Scan configuration files for security issues"""
        issues = []

        # Check main configuration
        config_file = self.project_root / "src" / "flowslide" / "core" / "simple_config.py"
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    content = f.read()

                # Check for insecure defaults
                if 'secret_key = "your-secret-key-here"' in content:
                    issues.append({
                        "type": "insecure_config",
                        "severity": "critical",
                        "file": str(config_file),
                        "description": "Default secret key detected",
                        "fix": "Generate a secure random secret key"
                    })

                if 'debug = True' in content:
                    issues.append({
                        "type": "insecure_config",
                        "severity": "medium",
                        "file": str(config_file),
                        "description": "Debug mode enabled by default",
                        "fix": "Disable debug mode in production"
                    })

            except Exception as e:
                print(f"Warning: Could not scan config file: {e}")

        return {"issues": issues, "total_issues": len(issues)}

    def scan_api_security(self) -> Dict[str, Any]:
        """Scan API endpoints for security issues"""
        issues = []

        # This would require running the application and testing endpoints
        # For now, we'll do static analysis

        api_files = list(self.project_root.glob("src/flowslide/api/*.py"))

        for api_file in api_files:
            try:
                with open(api_file, 'r') as f:
                    content = f.read()

                # Check for missing authentication
                if "@router." in content and "Depends(get_current_user)" not in content:
                    issues.append({
                        "type": "api_security",
                        "severity": "high",
                        "file": str(api_file),
                        "description": "API endpoints may lack authentication",
                        "fix": "Add authentication dependency to protected endpoints"
                    })

                # Check for SQL injection risks
                if "execute(" in content and "%" in content:
                    issues.append({
                        "type": "api_security",
                        "severity": "high",
                        "file": str(api_file),
                        "description": "Potential SQL injection risk",
                        "fix": "Use parameterized queries"
                    })

            except Exception as e:
                print(f"Warning: Could not scan {api_file}: {e}")

        return {"issues": issues, "total_issues": len(issues)}

    def scan_authentication(self) -> Dict[str, Any]:
        """Scan authentication implementation for security issues"""
        issues = []

        auth_file = self.project_root / "src" / "flowslide" / "auth" / "auth_service.py"
        if auth_file.exists():
            try:
                with open(auth_file, 'r') as f:
                    content = f.read()

                # Check password hashing
                if "hashlib.sha256" in content:
                    issues.append({
                        "type": "auth_security",
                        "severity": "critical",
                        "file": str(auth_file),
                        "description": "Weak password hashing algorithm (SHA256)",
                        "fix": "Use bcrypt or Argon2 for password hashing"
                    })

                # Check session security
                if "session_id" in content and "secure=False" in content:
                    issues.append({
                        "type": "auth_security",
                        "severity": "high",
                        "file": str(auth_file),
                        "description": "Insecure session cookies",
                        "fix": "Set secure=True for session cookies in production"
                    })

            except Exception as e:
                print(f"Warning: Could not scan auth file: {e}")

        return {"issues": issues, "total_issues": len(issues)}

    def save_results(self, results: Dict[str, Any]):
        """Save scan results to JSON file"""
        results_file = self.results_dir / f"security_scan_{self.timestamp}.json"

        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)

        print(f"\n📊 Results saved to {results_file}")

    def generate_report(self, results: Dict[str, Any]):
        """Generate HTML security report"""
        report_file = self.results_dir / f"security_report_{self.timestamp}.html"

        # Count issues by severity
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        total_issues = 0

        for scan_name, scan_result in results["scans"].items():
            if "issues" in scan_result:
                for issue in scan_result["issues"]:
                    severity = issue.get("severity", "unknown")
                    if severity in severity_counts:
                        severity_counts[severity] += 1
                    total_issues += 1

        # Generate HTML report
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>FlowSlide Security Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background: #f0f0f0; padding: 20px; border-radius: 5px; }}
                .summary {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin: 20px 0; }}
                .severity-box {{ padding: 15px; border-radius: 5px; text-align: center; color: white; }}
                .critical {{ background: #d32f2f; }}
                .high {{ background: #f57c00; }}
                .medium {{ background: #fbc02d; }}
                .low {{ background: #388e3c; }}
                .scan-result {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
                .issue {{ margin: 10px 0; padding: 10px; background: #f9f9f9; border-radius: 3px; }}
                .issue-critical {{ border-left: 5px solid #d32f2f; }}
                .issue-high {{ border-left: 5px solid #f57c00; }}
                .issue-medium {{ border-left: 5px solid #fbc02d; }}
                .issue-low {{ border-left: 5px solid #388e3c; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>FlowSlide Security Report</h1>
                <p>Generated: {results['timestamp']}</p>
                <p>Total Issues: {total_issues}</p>
            </div>

            <div class="summary">
                <div class="severity-box critical">
                    <h3>{severity_counts['critical']}</h3>
                    <p>Critical</p>
                </div>
                <div class="severity-box high">
                    <h3>{severity_counts['high']}</h3>
                    <p>High</p>
                </div>
                <div class="severity-box medium">
                    <h3>{severity_counts['medium']}</h3>
                    <p>Medium</p>
                </div>
                <div class="severity-box low">
                    <h3>{severity_counts['low']}</h3>
                    <p>Low</p>
                </div>
            </div>
        """

        # Add scan results
        for scan_name, scan_result in results["scans"].items():
            html_content += f"""
            <div class="scan-result">
                <h2>{scan_name.replace('_', ' ').title()}</h2>
            """

            if "error" in scan_result:
                html_content += f"<p><strong>Error:</strong> {scan_result['error']}</p>"
            elif "issues" in scan_result:
                if scan_result["issues"]:
                    for issue in scan_result["issues"]:
                        severity = issue.get("severity", "unknown")
                        html_content += f"""
                        <div class="issue issue-{severity}">
                            <h4>{issue.get('type', 'Unknown')}</h4>
                            <p><strong>Severity:</strong> {severity.title()}</p>
                            <p><strong>Description:</strong> {issue.get('description', 'No description')}</p>
                            <p><strong>Fix:</strong> {issue.get('fix', 'No fix provided')}</p>
                            {f"<p><strong>File:</strong> {issue['file']}</p>" if 'file' in issue else ""}
                            {f"<p><strong>Line:</strong> {issue['line']}</p>" if 'line' in issue else ""}
                        </div>
                        """
                else:
                    html_content += "<p>✅ No issues found</p>"

            html_content += "</div>"

        html_content += """
        </body>
        </html>
        """

        with open(report_file, 'w') as f:
            f.write(html_content)

        print(f"📋 Security report generated: {report_file}")


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="FlowSlide Security Scanner")
    parser.add_argument("--project-root", default=".", help="Project root directory")
    parser.add_argument("--scan", choices=["all", "deps", "code", "secrets", "docker", "config", "api", "auth"],
                       default="all", help="Specific scan to run")

    args = parser.parse_args()

    scanner = SecurityScanner(args.project_root)

    if args.scan == "all":
        results = scanner.run_all_scans()
    else:
        # Run specific scan
        scan_methods = {
            "deps": scanner.scan_dependencies,
            "code": scanner.scan_code_vulnerabilities,
            "secrets": scanner.scan_secrets,
            "docker": scanner.scan_docker_security,
            "config": scanner.scan_configuration,
            "api": scanner.scan_api_security,
            "auth": scanner.scan_authentication,
        }

        if args.scan in scan_methods:
            result = scan_methods[args.scan]()
            results = {"scans": {args.scan: result}}
            scanner.save_results(results)
            scanner.generate_report(results)

    # Print summary
    total_issues = sum(
        len(scan.get("issues", []))
        for scan in results["scans"].values()
        if "issues" in scan
    )

    print(f"\n🔒 Security scan completed")
    print(f"Total issues found: {total_issues}")

    if total_issues > 0:
        print("⚠️ Security issues detected. Please review the report.")
        sys.exit(1)
    else:
        print("✅ No security issues found!")
        sys.exit(0)


if __name__ == "__main__":
    main()
