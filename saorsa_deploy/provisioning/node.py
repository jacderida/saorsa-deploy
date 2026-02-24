from pyinfra.api import Config, Inventory, State
from pyinfra.api.connect import connect_all, disconnect_all
from pyinfra.api.operation import add_op
from pyinfra.api.operations import run_ops
from pyinfra.operations import server
from rich.console import Console

from saorsa_deploy.provisioning.genesis import (
    BINARY_INSTALL_PATH,
    RELEASE_ASSET_NAME,
    _get_latest_release_url,
)
from saorsa_deploy.provisioning.progress import (
    RichLiveProgressHandler,
    create_progress_handler,
)


def _build_node_exec_start(
    bootstrap_ip,
    bootstrap_port,
    port=None,
    ip_version="ipv4",
    log_level=None,
    testnet=False,
):
    """Build the ExecStart command line for a node service."""
    parts = [BINARY_INSTALL_PATH]
    parts.append(f"--bootstrap {bootstrap_ip}:{bootstrap_port}")
    if port is not None:
        parts.append(f"--port {port}")
    if ip_version:
        parts.append(f"--ip-version {ip_version}")
    if log_level:
        parts.append(f"--log-level {log_level}")
    parts.append("--disable-payment-verification")
    if testnet:
        parts.append("--network-mode testnet")
    return " ".join(parts)


def _build_node_unit_file(service_name, exec_start):
    """Build the systemd unit file content for a node service."""
    return f"""\
[Unit]
Description=Saorsa Node ({service_name})
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart={exec_start}
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
"""


class SaorsaNodeProvisioner:
    """Provisions saorsa-node services on multiple hosts using Pyinfra."""

    def __init__(
        self,
        host_ips: list[str],
        bootstrap_ip: str,
        bootstrap_port: int,
        ssh_key_path: str = "~/.ssh/id_rsa",
        node_count: int = 1,
        initial_port: int | None = None,
        ip_version: str = "ipv4",
        log_level: str | None = None,
        testnet: bool = False,
        console: Console | None = None,
    ):
        self.host_ips = host_ips
        self.bootstrap_ip = bootstrap_ip
        self.bootstrap_port = bootstrap_port
        self.ssh_key_path = ssh_key_path
        self.node_count = node_count
        self.initial_port = initial_port
        self.ip_version = ip_version
        self.log_level = log_level
        self.testnet = testnet
        self.console = console or Console()

    def execute(self) -> None:
        """Provision all hosts with saorsa-node services."""
        self.console.print("Fetching latest release from GitHub...")
        download_url = _get_latest_release_url()
        self.console.print(f"  Release URL: {download_url}")

        hosts_data = [
            (ip, {"ssh_user": "root", "ssh_key": self.ssh_key_path}) for ip in self.host_ips
        ]
        inventory = Inventory((hosts_data, {}))
        config = Config()
        state = State(inventory=inventory, config=config)

        progress = create_progress_handler(self.console)
        state.add_callback_handler(progress)

        if isinstance(progress, RichLiveProgressHandler):
            progress._live.start()

        try:
            self.console.print(f"Connecting to {len(self.host_ips)} host(s) as root...")
            connect_all(state)

            add_op(
                state,
                server.shell,
                name="Download and install saorsa-node binary",
                commands=[
                    f"wget -q {download_url} -O /tmp/{RELEASE_ASSET_NAME}",
                    f"tar -xzf /tmp/{RELEASE_ASSET_NAME} -C /tmp/",
                    f"mv /tmp/saorsa-node {BINARY_INSTALL_PATH}",
                    f"chmod +x {BINARY_INSTALL_PATH}",
                    f"rm -f /tmp/{RELEASE_ASSET_NAME}",
                ],
            )

            unit_commands = []
            service_names = []
            for i in range(self.node_count):
                service_name = f"saorsa-node-{i + 1}"
                service_names.append(service_name)
                node_port = (self.initial_port + i) if self.initial_port is not None else None
                exec_start = _build_node_exec_start(
                    bootstrap_ip=self.bootstrap_ip,
                    bootstrap_port=self.bootstrap_port,
                    port=node_port,
                    ip_version=self.ip_version,
                    log_level=self.log_level,
                    testnet=self.testnet,
                )
                unit_content = _build_node_unit_file(service_name, exec_start)
                unit_path = f"/etc/systemd/system/{service_name}.service"
                unit_commands.append(f"cat > {unit_path} << 'UNIT_EOF'\n{unit_content}UNIT_EOF")

            add_op(
                state,
                server.shell,
                name="Write systemd unit files",
                commands=unit_commands,
            )

            enable_commands = ["systemctl daemon-reload"]
            for service_name in service_names:
                enable_commands.append(f"systemctl enable --now {service_name}")

            add_op(
                state,
                server.shell,
                name="Enable and start node services",
                commands=enable_commands,
            )

            run_ops(state)

            if isinstance(progress, RichLiveProgressHandler):
                progress.mark_all_done()
        finally:
            disconnect_all(state)
            if isinstance(progress, RichLiveProgressHandler):
                progress._live.stop()

        failed = state.failed_hosts
        total = len(self.host_ips)
        succeeded = total - len(failed)
        self.console.print()
        self.console.print(
            f"[bold]Provisioning complete: {succeeded}/{total} hosts succeeded, "
            f"{self.node_count} node(s) per host[/bold]"
        )
        if failed:
            for host in failed:
                self.console.print(f"  [red]Failed: {host.name}[/red]")
            raise RuntimeError(f"{len(failed)} host(s) failed provisioning")
