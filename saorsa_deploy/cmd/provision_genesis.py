import sys

from rich.console import Console

from saorsa_deploy.provisioning.genesis import SaorsaGenesisNodeProvisioner
from saorsa_deploy.ssh import clear_known_hosts
from saorsa_deploy.state import load_deployment_state, update_deployment_state


def cmd_provision_genesis(args):
    """Execute the provision-genesis command: provision the genesis node."""
    console = Console()

    console.print(f"[bold]Loading deployment state for '{args.name}'...[/bold]")
    try:
        state = load_deployment_state(args.name)
    except RuntimeError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)

    bootstrap_ip = state.get("bootstrap_ip")
    if not bootstrap_ip:
        console.print(
            "[bold red]Error:[/bold red] No bootstrap IP found in deployment state. "
            "Was this deployment created with a recent version of the infra command?"
        )
        sys.exit(1)

    console.print(f"[bold]Provisioning genesis node at {bootstrap_ip}...[/bold]")
    console.print(f"  SSH key: {args.ssh_key_path}")
    console.print(f"  Port: {args.port}")
    if args.ip_version:
        console.print(f"  IP version: {args.ip_version}")
    if args.log_level:
        console.print(f"  Log level: {args.log_level}")
    if args.testnet:
        console.print("  Testnet mode: enabled")
    console.print()

    clear_known_hosts([bootstrap_ip], console)

    kwargs = {
        "ip": bootstrap_ip,
        "ssh_key_path": args.ssh_key_path,
        "port": args.port,
        "log_level": args.log_level,
        "testnet": args.testnet,
        "console": console,
    }
    if args.ip_version:
        kwargs["ip_version"] = args.ip_version
    node = SaorsaGenesisNodeProvisioner(**kwargs)

    try:
        node.execute()
        console.print()
        console.print("[bold green]Genesis node provisioned successfully.[/bold green]")
    except Exception as e:
        console.print(f"[bold red]Failed to provision genesis node:[/bold red] {e}")
        sys.exit(1)

    try:
        update_deployment_state(args.name, {"bootstrap_port": args.port})
        console.print("[dim]Bootstrap port saved to deployment state.[/dim]")
    except Exception as e:
        console.print(f"[yellow]Warning: Failed to save bootstrap port to state: {e}[/yellow]")
