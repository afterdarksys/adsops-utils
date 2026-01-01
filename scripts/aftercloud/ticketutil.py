#!/usr/bin/env python3
"""
AfterDark Change Management Ticketing Client

Client for changes.afterdarksys.com ticketing API.
Designed for accessibility with screen reader friendly output.

Usage:
    ticketutil.py list                     # List tickets
    ticketutil.py show <ticket-id>         # Show ticket details
    ticketutil.py create --config tkt.json # Create ticket
    ticketutil.py submit <ticket-id>       # Submit for approval
    ticketutil.py cancel <ticket-id>       # Cancel ticket
    ticketutil.py comment <ticket-id> msg  # Add comment
    ticketutil.py approvals                # List pending approvals
    ticketutil.py approve <approval-id>    # Approve change
    ticketutil.py configure                # Configure API credentials
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

try:
    import requests
except ImportError:
    print("Error: requests library not installed.")
    print("Install with: pip install requests")
    sys.exit(1)

# Import centralized config
try:
    from adsops_config import get_config
except ImportError:
    get_config = None


# Default API base URL
DEFAULT_API_URL = "https://changes.afterdarksys.com"

# Legacy config file location (deprecated - use ~/.adsops_config/config.json)
LEGACY_CONFIG_PATH = Path.home() / ".config" / "ticketutil" / "config.json"


def speak(message: str):
    """Print message with timestamp for screen readers."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")
    sys.stdout.flush()


def speak_plain(message: str):
    """Print without timestamp."""
    print(message)
    sys.stdout.flush()


def load_config() -> dict:
    """Load configuration from centralized config, env, or legacy file."""
    config = {
        "api_url": DEFAULT_API_URL,
        "api_token": None,
        "org_id": None,
    }

    # Try centralized config first
    if get_config is not None:
        cfg = get_config()
        if cfg.exists():
            config["api_url"] = cfg.get("ticketing", "api_url", DEFAULT_API_URL)
            config["api_token"] = cfg.get("ticketing", "api_token")
            config["org_id"] = cfg.get("ticketing", "org_id")

    # Environment variables override config file
    if os.environ.get("TICKETUTIL_API_URL"):
        config["api_url"] = os.environ.get("TICKETUTIL_API_URL")
    if os.environ.get("TICKETUTIL_API_TOKEN"):
        config["api_token"] = os.environ.get("TICKETUTIL_API_TOKEN")
    if os.environ.get("TICKETUTIL_ORG_ID"):
        config["org_id"] = os.environ.get("TICKETUTIL_ORG_ID")
    # Also support ADSOPS_ prefix
    if os.environ.get("ADSOPS_TICKETING_API_TOKEN"):
        config["api_token"] = os.environ.get("ADSOPS_TICKETING_API_TOKEN")

    # Fall back to legacy config if no token found
    if not config["api_token"] and LEGACY_CONFIG_PATH.exists():
        with open(LEGACY_CONFIG_PATH) as f:
            file_config = json.load(f)
            config.update(file_config)

    return config


def save_config(config: dict):
    """Save configuration to centralized config."""
    if get_config is not None:
        cfg = get_config()
        cfg.set("ticketing", "api_url", config.get("api_url", DEFAULT_API_URL))
        if config.get("api_token"):
            cfg.set("ticketing", "api_token", config["api_token"])
        if config.get("org_id"):
            cfg.set("ticketing", "org_id", config["org_id"])
    else:
        # Fall back to legacy config
        LEGACY_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LEGACY_CONFIG_PATH, "w") as f:
            json.dump(config, f, indent=2)
        LEGACY_CONFIG_PATH.chmod(0o600)


def get_api_client(config: dict):
    """Create configured requests session."""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Accept": "application/json",
    })

    if config.get("api_token"):
        session.headers["Authorization"] = f"Bearer {config['api_token']}"

    return session


def format_status(status: str) -> str:
    """Format ticket status for readability."""
    statuses = {
        "draft": "Draft",
        "submitted": "Submitted",
        "pending_approval": "Pending Approval",
        "approved": "Approved",
        "rejected": "Rejected",
        "in_progress": "In Progress",
        "completed": "Completed",
        "closed": "Closed",
        "cancelled": "Cancelled",
        "update_requested": "Update Requested",
    }
    return statuses.get(status, status)


def format_priority(priority: str) -> str:
    """Format priority for readability."""
    priorities = {
        "low": "Low",
        "medium": "Medium",
        "high": "High",
        "critical": "Critical",
        "emergency": "Emergency",
    }
    return priorities.get(priority, priority)


def format_datetime(dt_str: str) -> str:
    """Format datetime string for display."""
    if not dt_str:
        return "N/A"
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return dt_str


def configure(args):
    """Configure API credentials."""
    speak_plain("Ticketutil Configuration")
    speak_plain("=" * 60)
    speak_plain("")

    config = load_config()

    speak_plain("Enter your API credentials. Press Enter to keep existing values.")
    speak_plain("")

    # API URL
    current_url = config.get("api_url", DEFAULT_API_URL)
    speak_plain(f"Current API URL: {current_url}")
    new_url = input("API URL (or press Enter to keep current): ").strip()
    if new_url:
        config["api_url"] = new_url

    # API Token
    current_token = config.get("api_token", "")
    masked_token = f"{current_token[:8]}..." if current_token else "Not set"
    speak_plain(f"Current API Token: {masked_token}")
    new_token = input("API Token (or press Enter to keep current): ").strip()
    if new_token:
        config["api_token"] = new_token

    # Org ID
    current_org = config.get("org_id", "")
    speak_plain(f"Current Organization ID: {current_org or 'Not set'}")
    new_org = input("Organization ID (or press Enter to keep current): ").strip()
    if new_org:
        config["org_id"] = new_org

    save_config(config)
    speak_plain("")
    speak(f"Configuration saved to {CONFIG_PATH}")

    # Test connection
    speak("Testing API connection...")
    try:
        session = get_api_client(config)
        response = session.get(urljoin(config["api_url"], "/health"))
        if response.ok:
            speak("API connection successful!")
        else:
            speak(f"API returned status {response.status_code}")
    except Exception as e:
        speak(f"Connection test failed: {e}")


def list_tickets(args):
    """List tickets."""
    speak("Fetching tickets...")

    config = load_config()
    if not config.get("api_token"):
        print("Error: Not configured. Run 'ticketutil.py configure' first.")
        sys.exit(1)

    session = get_api_client(config)

    # Build query params
    params = {}
    if args.status:
        params["status"] = args.status
    if args.priority:
        params["priority"] = args.priority
    if args.search:
        params["search"] = args.search

    try:
        url = urljoin(config["api_url"], "/v1/tickets")
        response = session.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        tickets = data.get("tickets", [])
        total = data.get("total", len(tickets))

        if not tickets:
            speak_plain("")
            speak_plain("No tickets found.")
            return

        speak_plain("")
        speak_plain("Change Tickets")
        speak_plain("=" * 70)
        speak_plain("")

        for ticket in tickets:
            speak_plain(f"  ID: {ticket.get('id', 'N/A')}")
            speak_plain(f"    Title: {ticket.get('title', 'Untitled')}")
            speak_plain(f"    Status: {format_status(ticket.get('status', ''))}")
            speak_plain(f"    Priority: {format_priority(ticket.get('priority', ''))}")
            speak_plain(f"    Created: {format_datetime(ticket.get('created_at', ''))}")
            if ticket.get("assignee"):
                speak_plain(f"    Assignee: {ticket['assignee'].get('name', 'Unknown')}")
            speak_plain("")

        speak_plain(f"Total: {total} tickets")

    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        sys.exit(1)


def show_ticket(args):
    """Show ticket details."""
    speak(f"Fetching ticket {args.ticket_id}...")

    config = load_config()
    if not config.get("api_token"):
        print("Error: Not configured. Run 'ticketutil.py configure' first.")
        sys.exit(1)

    session = get_api_client(config)

    try:
        url = urljoin(config["api_url"], f"/v1/tickets/{args.ticket_id}")
        response = session.get(url)
        response.raise_for_status()
        data = response.json()

        ticket = data.get("ticket", {})

        speak_plain("")
        speak_plain("Change Ticket Details")
        speak_plain("=" * 70)
        speak_plain("")
        speak_plain(f"  ID: {ticket.get('id')}")
        speak_plain(f"  Ticket Number: {ticket.get('ticket_number', 'N/A')}")
        speak_plain(f"  Title: {ticket.get('title')}")
        speak_plain(f"  Status: {format_status(ticket.get('status'))}")
        speak_plain(f"  Priority: {format_priority(ticket.get('priority'))}")
        speak_plain(f"  Type: {ticket.get('type', 'N/A')}")

        speak_plain("")
        speak_plain("  Description:")
        description = ticket.get("description", "No description")
        for line in description.split("\n"):
            speak_plain(f"    {line}")

        speak_plain("")
        speak_plain("  Dates:")
        speak_plain(f"    Created: {format_datetime(ticket.get('created_at'))}")
        speak_plain(f"    Updated: {format_datetime(ticket.get('updated_at'))}")
        if ticket.get("scheduled_start"):
            speak_plain(f"    Scheduled Start: {format_datetime(ticket.get('scheduled_start'))}")
        if ticket.get("scheduled_end"):
            speak_plain(f"    Scheduled End: {format_datetime(ticket.get('scheduled_end'))}")

        speak_plain("")
        speak_plain("  People:")
        if ticket.get("created_by"):
            speak_plain(f"    Created By: {ticket['created_by'].get('name', 'Unknown')}")
        if ticket.get("assignee"):
            speak_plain(f"    Assignee: {ticket['assignee'].get('name', 'Unknown')}")

        # Risk assessment
        if ticket.get("risk_level"):
            speak_plain("")
            speak_plain("  Risk Assessment:")
            speak_plain(f"    Level: {ticket.get('risk_level')}")
            if ticket.get("impact"):
                speak_plain(f"    Impact: {ticket.get('impact')}")
            if ticket.get("rollback_plan"):
                speak_plain(f"    Rollback Plan: {ticket.get('rollback_plan')}")

        # Linked repositories
        repos = ticket.get("repositories", [])
        if repos:
            speak_plain("")
            speak_plain("  Linked Repositories:")
            for repo in repos:
                speak_plain(f"    - {repo.get('url', repo.get('name', 'Unknown'))}")

        speak_plain("")

    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        sys.exit(1)


def create_ticket(args):
    """Create a new ticket."""
    speak("Loading configuration...")

    config_path = Path(args.config).expanduser()
    if not config_path.exists():
        print(f"Error: Config file not found: {args.config}")
        sys.exit(1)

    with open(config_path) as f:
        ticket_config = json.load(f)

    config = load_config()
    if not config.get("api_token"):
        print("Error: Not configured. Run 'ticketutil.py configure' first.")
        sys.exit(1)

    session = get_api_client(config)

    speak(f"Creating ticket: {ticket_config.get('title', 'Untitled')}")

    try:
        url = urljoin(config["api_url"], "/v1/tickets")
        response = session.post(url, json=ticket_config)
        response.raise_for_status()
        data = response.json()

        ticket = data.get("ticket", {})

        speak("Ticket created successfully!")
        speak_plain("")
        speak_plain(f"  Ticket ID: {ticket.get('id')}")
        speak_plain(f"  Ticket Number: {ticket.get('ticket_number', 'N/A')}")
        speak_plain(f"  Status: {format_status(ticket.get('status'))}")
        speak_plain("")

        if args.submit:
            speak("Submitting ticket for approval...")
            submit_url = urljoin(config["api_url"], f"/v1/tickets/{ticket['id']}/submit")
            submit_response = session.post(submit_url)
            submit_response.raise_for_status()
            speak("Ticket submitted for approval!")

    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        if hasattr(e, "response") and e.response is not None:
            try:
                error_data = e.response.json()
                print(f"Details: {error_data.get('error', str(error_data))}")
            except Exception:
                pass
        sys.exit(1)


def submit_ticket(args):
    """Submit ticket for approval."""
    speak(f"Submitting ticket {args.ticket_id} for approval...")

    config = load_config()
    if not config.get("api_token"):
        print("Error: Not configured. Run 'ticketutil.py configure' first.")
        sys.exit(1)

    session = get_api_client(config)

    try:
        url = urljoin(config["api_url"], f"/v1/tickets/{args.ticket_id}/submit")
        response = session.post(url)
        response.raise_for_status()

        speak("Ticket submitted for approval!")

    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        sys.exit(1)


def cancel_ticket(args):
    """Cancel a ticket."""
    speak(f"Cancelling ticket {args.ticket_id}...")

    config = load_config()
    if not config.get("api_token"):
        print("Error: Not configured. Run 'ticketutil.py configure' first.")
        sys.exit(1)

    session = get_api_client(config)

    try:
        url = urljoin(config["api_url"], f"/v1/tickets/{args.ticket_id}/cancel")
        response = session.post(url, json={"reason": args.reason})
        response.raise_for_status()

        speak("Ticket cancelled!")

    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        sys.exit(1)


def add_comment(args):
    """Add a comment to a ticket."""
    speak(f"Adding comment to ticket {args.ticket_id}...")

    config = load_config()
    if not config.get("api_token"):
        print("Error: Not configured. Run 'ticketutil.py configure' first.")
        sys.exit(1)

    session = get_api_client(config)

    try:
        url = urljoin(config["api_url"], f"/v1/tickets/{args.ticket_id}/comments")
        response = session.post(url, json={"content": args.message})
        response.raise_for_status()

        speak("Comment added!")

    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        sys.exit(1)


def list_approvals(args):
    """List pending approvals."""
    speak("Fetching pending approvals...")

    config = load_config()
    if not config.get("api_token"):
        print("Error: Not configured. Run 'ticketutil.py configure' first.")
        sys.exit(1)

    session = get_api_client(config)

    try:
        url = urljoin(config["api_url"], "/v1/approvals")
        response = session.get(url)
        response.raise_for_status()
        data = response.json()

        approvals = data.get("approvals", [])

        if not approvals:
            speak_plain("")
            speak_plain("No pending approvals.")
            return

        speak_plain("")
        speak_plain("Pending Approvals")
        speak_plain("=" * 70)
        speak_plain("")

        for approval in approvals:
            speak_plain(f"  Approval ID: {approval.get('id')}")
            ticket = approval.get("ticket", {})
            speak_plain(f"    Ticket: {ticket.get('title', 'Unknown')}")
            speak_plain(f"    Ticket Number: {ticket.get('ticket_number', 'N/A')}")
            speak_plain(f"    Status: {approval.get('status', 'pending')}")
            speak_plain(f"    Requested: {format_datetime(approval.get('created_at'))}")
            if approval.get("requester"):
                speak_plain(f"    Requester: {approval['requester'].get('name', 'Unknown')}")
            speak_plain("")

        speak_plain(f"Total: {len(approvals)} pending approvals")

    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        sys.exit(1)


def approve_change(args):
    """Approve a change request."""
    speak(f"Approving change {args.approval_id}...")

    config = load_config()
    if not config.get("api_token"):
        print("Error: Not configured. Run 'ticketutil.py configure' first.")
        sys.exit(1)

    session = get_api_client(config)

    try:
        url = urljoin(config["api_url"], f"/v1/approvals/{args.approval_id}/approve")
        response = session.post(url, json={"comment": args.comment})
        response.raise_for_status()

        speak("Change approved!")

    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        sys.exit(1)


def deny_change(args):
    """Deny a change request."""
    speak(f"Denying change {args.approval_id}...")

    config = load_config()
    if not config.get("api_token"):
        print("Error: Not configured. Run 'ticketutil.py configure' first.")
        sys.exit(1)

    session = get_api_client(config)

    try:
        url = urljoin(config["api_url"], f"/v1/approvals/{args.approval_id}/deny")
        response = session.post(url, json={"reason": args.reason})
        response.raise_for_status()

        speak("Change denied.")

    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        sys.exit(1)


def export_template(args):
    """Export ticket configuration template."""
    template = {
        "_comment": "Change Ticket Template",
        "_instructions": [
            "1. Fill in the required fields: title, description, type",
            "2. Set priority based on urgency",
            "3. Add scheduled dates for planned changes",
            "4. Run: ticketutil.py create --config this-file.json"
        ],
        "title": "Brief description of the change",
        "description": "Detailed description of what will be changed and why",
        "type": "standard",
        "priority": "medium",
        "risk_level": "low",
        "impact": "Description of potential impact",
        "rollback_plan": "Steps to rollback if needed",
        "scheduled_start": "2025-01-15T10:00:00Z",
        "scheduled_end": "2025-01-15T12:00:00Z",
        "submit": False
    }

    output_path = Path(args.output).expanduser()
    with open(output_path, "w") as f:
        json.dump(template, f, indent=2)

    speak_plain(f"Template saved to: {args.output}")
    speak_plain("")
    speak_plain("Ticket types: standard, normal, emergency, expedited")
    speak_plain("Priority levels: low, medium, high, critical, emergency")
    speak_plain("Risk levels: low, medium, high")


def main():
    parser = argparse.ArgumentParser(
        description="AfterDark Change Management Ticketing Client. Accessible for screen readers.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    ticketutil.py configure                  # Set up API credentials
    ticketutil.py list                       # List all tickets
    ticketutil.py list --status submitted    # List submitted tickets
    ticketutil.py show <ticket-id>           # Show ticket details
    ticketutil.py create --config ticket.json # Create ticket
    ticketutil.py submit <ticket-id>         # Submit for approval
    ticketutil.py comment <ticket-id> "msg"  # Add comment
    ticketutil.py approvals                  # List pending approvals
    ticketutil.py approve <approval-id>      # Approve change
    ticketutil.py deny <approval-id> --reason "..." # Deny change

Environment Variables:
    TICKETUTIL_API_URL    - API base URL (default: https://changes.afterdarksys.com)
    TICKETUTIL_API_TOKEN  - API authentication token
    TICKETUTIL_ORG_ID     - Organization ID

Screen Reader Notes:
    All output is plain text with clear labels.
    Status messages include timestamps.
"""
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # configure
    config_parser = subparsers.add_parser("configure", help="Configure API credentials")
    config_parser.set_defaults(func=configure)

    # list
    list_parser = subparsers.add_parser("list", help="List tickets")
    list_parser.add_argument("--status", help="Filter by status")
    list_parser.add_argument("--priority", help="Filter by priority")
    list_parser.add_argument("--search", help="Search term")
    list_parser.set_defaults(func=list_tickets)

    # show
    show_parser = subparsers.add_parser("show", help="Show ticket details")
    show_parser.add_argument("ticket_id", help="Ticket ID or number")
    show_parser.set_defaults(func=show_ticket)

    # create
    create_parser = subparsers.add_parser("create", help="Create ticket")
    create_parser.add_argument("--config", required=True, help="Config file path")
    create_parser.add_argument("--submit", "-s", action="store_true", help="Submit after creating")
    create_parser.set_defaults(func=create_ticket)

    # submit
    submit_parser = subparsers.add_parser("submit", help="Submit ticket for approval")
    submit_parser.add_argument("ticket_id", help="Ticket ID")
    submit_parser.set_defaults(func=submit_ticket)

    # cancel
    cancel_parser = subparsers.add_parser("cancel", help="Cancel ticket")
    cancel_parser.add_argument("ticket_id", help="Ticket ID")
    cancel_parser.add_argument("--reason", "-r", help="Cancellation reason")
    cancel_parser.set_defaults(func=cancel_ticket)

    # comment
    comment_parser = subparsers.add_parser("comment", help="Add comment to ticket")
    comment_parser.add_argument("ticket_id", help="Ticket ID")
    comment_parser.add_argument("message", help="Comment message")
    comment_parser.set_defaults(func=add_comment)

    # approvals
    approvals_parser = subparsers.add_parser("approvals", help="List pending approvals")
    approvals_parser.set_defaults(func=list_approvals)

    # approve
    approve_parser = subparsers.add_parser("approve", help="Approve change")
    approve_parser.add_argument("approval_id", help="Approval ID")
    approve_parser.add_argument("--comment", "-c", help="Approval comment")
    approve_parser.set_defaults(func=approve_change)

    # deny
    deny_parser = subparsers.add_parser("deny", help="Deny change")
    deny_parser.add_argument("approval_id", help="Approval ID")
    deny_parser.add_argument("--reason", "-r", required=True, help="Denial reason")
    deny_parser.set_defaults(func=deny_change)

    # export-template
    template_parser = subparsers.add_parser("export-template", help="Export ticket template")
    template_parser.add_argument("output", help="Output file path")
    template_parser.set_defaults(func=export_template)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        args.func(args)
    except KeyboardInterrupt:
        speak("")
        speak("Operation cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
