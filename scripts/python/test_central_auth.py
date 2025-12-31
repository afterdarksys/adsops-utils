#!/usr/bin/env python3
"""
test_central_auth.py - Central Authentication Testing Tool
After Dark Systems - Ops Utils

Test authentication against central auth service, list services,
and manage passwords.
"""

import argparse
import getpass
import json
import sys
from typing import Optional
import urllib.request
import urllib.error
import urllib.parse
import ssl

from common import Colors, log_error, log_info, log_success, log_warn


DEFAULT_SERVER = "login.afterdarksys.com"
DEFAULT_TIMEOUT = 30


class CentralAuthClient:
    """Client for interacting with Central Auth service."""

    def __init__(self, server: str, verify_ssl: bool = True):
        self.server = server
        self.base_url = f"https://{server}"
        self.token: Optional[str] = None
        self.verify_ssl = verify_ssl

        # SSL context
        if verify_ssl:
            self.ssl_context = ssl.create_default_context()
        else:
            self.ssl_context = ssl.create_default_context()
            self.ssl_context.check_hostname = False
            self.ssl_context.verify_mode = ssl.CERT_NONE

    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict] = None,
        headers: Optional[dict] = None
    ) -> dict:
        """Make HTTP request to the auth server."""
        url = f"{self.base_url}{endpoint}"
        req_headers = {"Content-Type": "application/json"}

        if self.token:
            req_headers["Authorization"] = f"Bearer {self.token}"

        if headers:
            req_headers.update(headers)

        body = json.dumps(data).encode("utf-8") if data else None

        request = urllib.request.Request(
            url,
            data=body,
            headers=req_headers,
            method=method
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=DEFAULT_TIMEOUT,
                context=self.ssl_context
            ) as response:
                response_data = response.read().decode("utf-8")
                if response_data:
                    return json.loads(response_data)
                return {"status": "ok"}
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else ""
            try:
                error_data = json.loads(error_body) if error_body else {}
            except json.JSONDecodeError:
                error_data = {"message": error_body}
            raise AuthError(e.code, error_data.get("message", str(e)))
        except urllib.error.URLError as e:
            raise AuthError(0, f"Connection failed: {e.reason}")

    def login(self, username: str, password: str, is_admin: bool = False) -> dict:
        """Authenticate with central auth service."""
        endpoint = "/api/v1/auth/login"
        if is_admin:
            endpoint = "/api/v1/admin/login"

        data = {
            "username": username,
            "password": password
        }

        result = self._request("POST", endpoint, data)

        if "token" in result:
            self.token = result["token"]
        elif "access_token" in result:
            self.token = result["access_token"]

        return result

    def list_services(self) -> list:
        """List available services."""
        result = self._request("GET", "/api/v1/services")
        return result.get("services", result.get("data", []))

    def test_service(self, service_name: str) -> dict:
        """Test authentication against a specific service."""
        result = self._request("POST", f"/api/v1/services/{service_name}/test")
        return result

    def get_service_info(self, service_name: str) -> dict:
        """Get information about a specific service."""
        result = self._request("GET", f"/api/v1/services/{service_name}")
        return result

    def change_password(
        self,
        current_password: str,
        new_password: str
    ) -> dict:
        """Change the user's password."""
        data = {
            "current_password": current_password,
            "new_password": new_password
        }
        result = self._request("POST", "/api/v1/auth/password", data)
        return result

    def admin_reset_password(
        self,
        target_username: str,
        new_password: str
    ) -> dict:
        """Admin: Reset another user's password."""
        data = {
            "username": target_username,
            "new_password": new_password
        }
        result = self._request("POST", "/api/v1/admin/reset-password", data)
        return result

    def whoami(self) -> dict:
        """Get current user info."""
        return self._request("GET", "/api/v1/auth/whoami")


class AuthError(Exception):
    """Authentication error."""
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


def print_services(services: list) -> None:
    """Print services in a formatted table."""
    if not services:
        log_warn("No services found")
        return

    print(f"\n{Colors.BLUE}Available Services:{Colors.NC}")
    print("-" * 60)
    print(f"{'Name':<25} {'Status':<15} {'Description'}")
    print("-" * 60)

    for svc in services:
        if isinstance(svc, dict):
            name = svc.get("name", svc.get("id", "unknown"))
            status = svc.get("status", "active")
            desc = svc.get("description", "")
        else:
            name = str(svc)
            status = "active"
            desc = ""

        status_color = Colors.GREEN if status == "active" else Colors.YELLOW
        print(f"{name:<25} {status_color}{status:<15}{Colors.NC} {desc}")

    print("-" * 60)
    print(f"Total: {len(services)} service(s)\n")


def interactive_service_select(services: list) -> Optional[str]:
    """Let user select a service interactively."""
    if not services:
        return None

    print(f"\n{Colors.BLUE}Select a service to test:{Colors.NC}")
    for i, svc in enumerate(services, 1):
        if isinstance(svc, dict):
            name = svc.get("name", svc.get("id", "unknown"))
        else:
            name = str(svc)
        print(f"  {i}. {name}")
    print(f"  0. Cancel")

    while True:
        try:
            choice = input("\nEnter number: ").strip()
            if choice == "0" or choice == "":
                return None
            idx = int(choice) - 1
            if 0 <= idx < len(services):
                svc = services[idx]
                return svc.get("name", svc.get("id", str(svc))) if isinstance(svc, dict) else str(svc)
            print(f"{Colors.RED}Invalid selection{Colors.NC}")
        except ValueError:
            print(f"{Colors.RED}Please enter a number{Colors.NC}")
        except KeyboardInterrupt:
            print()
            return None


def prompt_password_change() -> tuple[str, str]:
    """Prompt for current and new password."""
    print(f"\n{Colors.BLUE}Password Change{Colors.NC}")
    current = getpass.getpass("Current password: ")
    new_pass = getpass.getpass("New password: ")
    confirm = getpass.getpass("Confirm new password: ")

    if new_pass != confirm:
        raise ValueError("Passwords do not match")

    if len(new_pass) < 8:
        raise ValueError("Password must be at least 8 characters")

    return current, new_pass


def prompt_admin_reset() -> tuple[str, str]:
    """Prompt for admin password reset."""
    print(f"\n{Colors.BLUE}Admin Password Reset{Colors.NC}")
    target_user = input("Target username: ").strip()
    if not target_user:
        raise ValueError("Username required")

    new_pass = getpass.getpass("New password for user: ")
    confirm = getpass.getpass("Confirm new password: ")

    if new_pass != confirm:
        raise ValueError("Passwords do not match")

    return target_user, new_pass


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test Central Authentication Service",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Login and list services
  %(prog)s -u myuser -l

  # Login and test specific service
  %(prog)s -u myuser --service myapp

  # Login as admin
  %(prog)s -u admin --isadmin

  # Change password
  %(prog)s -u myuser -cpw

  # Use different server
  %(prog)s -s auth.example.com -u myuser -l
"""
    )

    parser.add_argument(
        "-s", "--server",
        default=DEFAULT_SERVER,
        help=f"Auth server hostname (default: {DEFAULT_SERVER})"
    )
    parser.add_argument(
        "-u", "--username",
        required=True,
        help="Username for authentication"
    )
    parser.add_argument(
        "--service", "-svc",
        help="Service name to test authentication against"
    )
    parser.add_argument(
        "-l", "--list-services",
        action="store_true",
        help="List available services"
    )
    parser.add_argument(
        "-cpw", "--change-password",
        action="store_true",
        help="Change password after login"
    )
    parser.add_argument(
        "--isadmin", "-is",
        action="store_true",
        help="Login as administrator"
    )
    parser.add_argument(
        "--reset-user",
        metavar="USERNAME",
        help="Admin: Reset password for specified user"
    )
    parser.add_argument(
        "-k", "--insecure",
        action="store_true",
        help="Disable SSL certificate verification"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )

    args = parser.parse_args()

    # Prompt for password
    print(f"\n{Colors.BLUE}Central Auth Test - {args.server}{Colors.NC}")
    print("-" * 40)
    password = getpass.getpass(f"Password for {args.username}: ")

    if not password:
        log_error("Password required")
        sys.exit(1)

    # Create client
    client = CentralAuthClient(args.server, verify_ssl=not args.insecure)

    # Login
    try:
        log_info(f"Authenticating as {args.username}...")
        if args.isadmin:
            log_info("Using admin login endpoint")

        result = client.login(args.username, password, is_admin=args.isadmin)
        log_success("Authentication successful")

        if args.verbose:
            print(f"\n{Colors.BLUE}Login Response:{Colors.NC}")
            print(json.dumps(result, indent=2))

        # Show user info
        try:
            user_info = client.whoami()
            print(f"\n{Colors.GREEN}Logged in as:{Colors.NC} {user_info.get('username', args.username)}")
            if user_info.get("roles"):
                print(f"{Colors.GREEN}Roles:{Colors.NC} {', '.join(user_info['roles'])}")
        except AuthError:
            pass  # whoami endpoint may not exist

    except AuthError as e:
        log_error(f"Authentication failed: {e.message}")
        sys.exit(1)

    # List services
    if args.list_services:
        try:
            log_info("Fetching services...")
            services = client.list_services()
            print_services(services)

            # Interactive service selection if no specific service requested
            if not args.service and services:
                selected = interactive_service_select(services)
                if selected:
                    args.service = selected

        except AuthError as e:
            log_error(f"Failed to list services: {e.message}")

    # Test specific service
    if args.service:
        try:
            log_info(f"Testing access to service: {args.service}")
            result = client.test_service(args.service)
            log_success(f"Access to '{args.service}' verified")

            if args.verbose:
                print(json.dumps(result, indent=2))

        except AuthError as e:
            log_error(f"Service test failed: {e.message}")

    # Admin: Reset another user's password
    if args.reset_user:
        if not args.isadmin:
            log_error("--reset-user requires --isadmin flag")
            sys.exit(1)

        try:
            new_pass = getpass.getpass(f"New password for {args.reset_user}: ")
            confirm = getpass.getpass("Confirm new password: ")

            if new_pass != confirm:
                log_error("Passwords do not match")
                sys.exit(1)

            log_info(f"Resetting password for user: {args.reset_user}")
            result = client.admin_reset_password(args.reset_user, new_pass)
            log_success(f"Password reset successful for {args.reset_user}")

        except AuthError as e:
            log_error(f"Password reset failed: {e.message}")
            sys.exit(1)

    # Change own password
    if args.change_password:
        try:
            current_pass, new_pass = prompt_password_change()
            log_info("Changing password...")
            result = client.change_password(current_pass, new_pass)
            log_success("Password changed successfully")

        except ValueError as e:
            log_error(str(e))
            sys.exit(1)
        except AuthError as e:
            log_error(f"Password change failed: {e.message}")
            sys.exit(1)

    print(f"\n{Colors.GREEN}Session complete{Colors.NC}\n")


if __name__ == "__main__":
    main()
