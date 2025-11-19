#!/usr/bin/env python3
"""
ERP Sync - Bidirectional synchronization for Frappe/ERPNext instances
"""
import argparse
import os
import sys
from datetime import datetime
from colorama import init as colorama_init, Fore, Style
from dotenv import load_dotenv

from models import init_db, get_db, SyncRecord, SyncLog, ConflictRecord
from frappe_client import FrappeClient
from sync_engine import SyncEngine
from webhook_server import start_webhook_server

colorama_init()

# Load environment variables
load_dotenv()


def print_banner():
    """Print application banner"""
    banner = f"""
{Fore.CYAN}{'='*60}
    _____ ____  ____    ____
   / ____|  _ \\|  _ \\  / ___| _   _ _ __   ___
  | |  _| |_) | |_) | \\___ \\| | | | '_ \\ / __|
  | |_| |  _ <|  __/   ___) | |_| | | | | (__
   \\____|_| \\_\\_|     |____/ \\__, |_| |_|\\___|
                              |___/
    Bidirectional ERP Synchronization System
{'='*60}{Style.RESET_ALL}
"""
    print(banner)


def cmd_init(args):
    """Initialize database"""
    print(f"{Fore.YELLOW}Initializing database...{Style.RESET_ALL}")
    init_db()
    print(f"{Fore.GREEN}[OK] Database initialized successfully{Style.RESET_ALL}")


def cmd_test(args):
    """Test connections to both ERP systems"""
    print(f"{Fore.YELLOW}Testing connections...{Style.RESET_ALL}\n")

    cloud = FrappeClient(
        url=os.getenv('CLOUD_ERP_URL'),
        api_key=os.getenv('CLOUD_API_KEY'),
        api_secret=os.getenv('CLOUD_API_SECRET'),
        instance_name='Cloud'
    )

    local = FrappeClient(
        url=os.getenv('LOCAL_ERP_URL'),
        api_key=os.getenv('LOCAL_API_KEY'),
        api_secret=os.getenv('LOCAL_API_SECRET'),
        instance_name='Local'
    )

    cloud_ok = cloud.test_connection()
    local_ok = local.test_connection()

    if cloud_ok and local_ok:
        print(f"\n{Fore.GREEN}[OK] All connections successful{Style.RESET_ALL}")
        return 0
    else:
        print(f"\n{Fore.RED}[FAIL] Connection test failed{Style.RESET_ALL}")
        return 1


def cmd_sync(args):
    """Run synchronization"""
    print(f"{Fore.YELLOW}Starting synchronization...{Style.RESET_ALL}\n")

    # Initialize clients
    cloud = FrappeClient(
        url=os.getenv('CLOUD_ERP_URL'),
        api_key=os.getenv('CLOUD_API_KEY'),
        api_secret=os.getenv('CLOUD_API_SECRET'),
        instance_name='Cloud'
    )

    local = FrappeClient(
        url=os.getenv('LOCAL_ERP_URL'),
        api_key=os.getenv('LOCAL_API_KEY'),
        api_secret=os.getenv('LOCAL_API_SECRET'),
        instance_name='Local'
    )

    # Initialize sync engine
    engine = SyncEngine(cloud, local)

    # Sync specific document or all
    if args.doctype and args.docname:
        print(f"Syncing {args.doctype}/{args.docname}...")
        success, message = engine.sync_document(args.doctype, args.docname, args.direction)

        if success:
            print(f"{Fore.GREEN}[OK] {message}{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}[FAIL] {message}{Style.RESET_ALL}")

    elif args.doctype:
        print(f"Syncing all {args.doctype} documents...")
        stats = engine.sync_doctype(args.doctype, limit=args.limit)
        print_sync_stats(stats)

    else:
        print("Syncing all configured DocTypes...")
        stats = engine.sync_all_doctypes(limit=args.limit)
        print_sync_stats(stats)


def cmd_webhook(args):
    """Start webhook server"""
    print(f"{Fore.YELLOW}Starting webhook server...{Style.RESET_ALL}\n")

    # Initialize clients
    cloud = FrappeClient(
        url=os.getenv('CLOUD_ERP_URL'),
        api_key=os.getenv('CLOUD_API_KEY'),
        api_secret=os.getenv('CLOUD_API_SECRET'),
        instance_name='Cloud'
    )

    local = FrappeClient(
        url=os.getenv('LOCAL_ERP_URL'),
        api_key=os.getenv('LOCAL_API_KEY'),
        api_secret=os.getenv('LOCAL_API_SECRET'),
        instance_name='Local'
    )

    # Test connections first
    if not cloud.test_connection() or not local.test_connection():
        print(f"{Fore.RED}[FAIL] Connection test failed. Please check your configuration.{Style.RESET_ALL}")
        return 1

    # Start webhook server
    start_webhook_server(cloud, local)


def cmd_status(args):
    """Show sync status"""
    db = get_db()
    try:
        print(f"{Fore.CYAN}Sync Status{Style.RESET_ALL}\n")

        # Total sync records
        total_records = db.query(SyncRecord).count()
        synced = db.query(SyncRecord).filter_by(sync_status='synced').count()
        errors = db.query(SyncRecord).filter_by(sync_status='error').count()
        conflicts = db.query(SyncRecord).filter_by(sync_status='conflict').count()

        print(f"Total Documents Tracked: {total_records}")
        print(f"  {Fore.GREEN}Synced: {synced}{Style.RESET_ALL}")
        print(f"  {Fore.RED}Errors: {errors}{Style.RESET_ALL}")
        print(f"  {Fore.YELLOW}Conflicts: {conflicts}{Style.RESET_ALL}")

        # Recent sync logs
        print(f"\n{Fore.CYAN}Recent Sync Operations:{Style.RESET_ALL}")
        recent_logs = db.query(SyncLog).order_by(
            SyncLog.timestamp.desc()
        ).limit(10).all()

        for log in recent_logs:
            status_color = Fore.GREEN if log.status == 'success' else Fore.RED
            print(f"  [{log.timestamp.strftime('%H:%M:%S')}] "
                  f"{status_color}{log.status.upper()}{Style.RESET_ALL} - "
                  f"{log.doctype}/{log.docname} ({log.direction})")

        # Unresolved conflicts
        unresolved = db.query(ConflictRecord).filter_by(resolved=False).count()
        if unresolved > 0:
            print(f"\n{Fore.YELLOW}WARNING: Unresolved Conflicts: {unresolved}{Style.RESET_ALL}")

    finally:
        db.close()


def cmd_conflicts(args):
    """Show and resolve conflicts"""
    db = get_db()
    try:
        conflicts = db.query(ConflictRecord).filter_by(resolved=False).all()

        if not conflicts:
            print(f"{Fore.GREEN}No unresolved conflicts{Style.RESET_ALL}")
            return

        print(f"{Fore.YELLOW}Unresolved Conflicts: {len(conflicts)}{Style.RESET_ALL}\n")

        for i, conflict in enumerate(conflicts, 1):
            print(f"{i}. {conflict.doctype}/{conflict.docname}")
            print(f"   Cloud modified: {conflict.cloud_modified}")
            print(f"   Local modified: {conflict.local_modified}")
            print()

        if args.resolve:
            # TODO: Implement interactive conflict resolution
            print("Interactive conflict resolution coming soon...")

    finally:
        db.close()


def cmd_setup_webhook(args):
    """Show instructions for setting up webhooks"""
    webhook_url = f"http://{os.getenv('WEBHOOK_HOST', '0.0.0.0')}:{os.getenv('WEBHOOK_PORT', 5000)}"
    secret = os.getenv('WEBHOOK_SECRET')

    print(f"{Fore.CYAN}Webhook Setup Instructions{Style.RESET_ALL}\n")

    print("1. Start the webhook server:")
    print(f"   {Fore.GREEN}python main.py webhook{Style.RESET_ALL}\n")

    print("2. Configure webhooks in CLOUD ERP:")
    print(f"   - Login to {os.getenv('CLOUD_ERP_URL')}")
    print("   - Go to: Setup > Integrations > Webhook")
    print("   - Create new webhook:")
    print(f"     • Request URL: {webhook_url}/webhook/cloud")
    print(f"     • Webhook Secret: {secret}")
    print("     • Document Type: Select DocType (e.g., Customer)")
    print("     • Enable: After Insert, After Save, After Delete")
    print()

    print("3. Configure webhooks in LOCAL ERP:")
    print(f"   - Login to {os.getenv('LOCAL_ERP_URL')}")
    print("   - Go to: Setup > Integrations > Webhook")
    print("   - Create new webhook:")
    print(f"     • Request URL: {webhook_url}/webhook/local")
    print(f"     • Webhook Secret: {secret}")
    print("     • Document Type: Select DocType (e.g., Customer)")
    print("     • Enable: After Insert, After Save, After Delete")
    print()

    print(f"{Fore.YELLOW}Note: If your local machine is behind NAT, you may need to use ngrok or similar tool")
    print(f"      to expose the webhook endpoint to your cloud ERP.{Style.RESET_ALL}")


def print_sync_stats(stats):
    """Print sync statistics"""
    print(f"\n{Fore.CYAN}Sync Statistics:{Style.RESET_ALL}")
    print(f"  Total: {stats['total']}")
    print(f"  {Fore.GREEN}Success: {stats['success']}{Style.RESET_ALL}")
    print(f"  {Fore.YELLOW}Skipped: {stats['skipped']}{Style.RESET_ALL}")
    print(f"  {Fore.YELLOW}Conflicts: {stats['conflicts']}{Style.RESET_ALL}")
    print(f"  {Fore.RED}Failed: {stats['failed']}{Style.RESET_ALL}")


def main():
    """Main CLI entry point"""
    print_banner()

    parser = argparse.ArgumentParser(
        description='Bidirectional ERP Synchronization System',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Init command
    parser_init = subparsers.add_parser('init', help='Initialize database')
    parser_init.set_defaults(func=cmd_init)

    # Test command
    parser_test = subparsers.add_parser('test', help='Test connections')
    parser_test.set_defaults(func=cmd_test)

    # Sync command
    parser_sync = subparsers.add_parser('sync', help='Run synchronization')
    parser_sync.add_argument('--doctype', help='Specific DocType to sync')
    parser_sync.add_argument('--docname', help='Specific document name to sync')
    parser_sync.add_argument('--direction', choices=['auto', 'cloud_to_local', 'local_to_cloud'],
                           default='auto', help='Sync direction')
    parser_sync.add_argument('--limit', type=int, default=100, help='Max documents to sync')
    parser_sync.set_defaults(func=cmd_sync)

    # Webhook command
    parser_webhook = subparsers.add_parser('webhook', help='Start webhook server')
    parser_webhook.set_defaults(func=cmd_webhook)

    # Status command
    parser_status = subparsers.add_parser('status', help='Show sync status')
    parser_status.set_defaults(func=cmd_status)

    # Conflicts command
    parser_conflicts = subparsers.add_parser('conflicts', help='Show conflicts')
    parser_conflicts.add_argument('--resolve', action='store_true', help='Resolve conflicts interactively')
    parser_conflicts.set_defaults(func=cmd_conflicts)

    # Setup webhook command
    parser_setup = subparsers.add_parser('setup-webhook', help='Show webhook setup instructions')
    parser_setup.set_defaults(func=cmd_setup_webhook)

    # Parse arguments
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Run command
    try:
        return args.func(args) or 0
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Interrupted by user{Style.RESET_ALL}")
        return 130
    except Exception as e:
        print(f"{Fore.RED}Error: {e}{Style.RESET_ALL}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
