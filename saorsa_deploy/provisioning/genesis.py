from io import StringIO

import requests
from pyinfra.api import Config, Inventory, State
from pyinfra.api.connect import connect_all, disconnect_all
from pyinfra.api.operation import add_op
from pyinfra.api.operations import run_ops
from pyinfra.operations import files, server, systemd
from rich.console import Console

GITHUB_REPO = "saorsa-labs/saorsa-node"
RELEASE_ASSET_NAME = "saorsa-node-cli-linux-x64.tar.gz"
BINARY_INSTALL_PATH = "/usr/local/bin/saorsa-node"
SERVICE_NAME = "saorsa-genesis-node"
UNIT_FILE_PATH = f"/etc/systemd/system/{SERVICE_NAME}.service"


def _get_latest_release_url() -> str:
    """Fetch the download URL for the latest saorsa-node release from GitHub."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    release = resp.json()
    for asset in release.get("assets", []):
        if asset["name"] == RELEASE_ASSET_NAME:
            return asset["browser_download_url"]
    raise RuntimeError(
        f"Could not find asset '{RELEASE_ASSET_NAME}' in latest release of {GITHUB_REPO}"
    )


def _build_exec_start(port=None, ip_version="ipv4", log_level=None, testnet=False) -> str:
    """Build the ExecStart command line for the systemd service."""
    parts = [BINARY_INSTALL_PATH]
    if port:
        parts.append(f"--port {port}")
    if ip_version:
        parts.append(f"--ip-version {ip_version}")
    if log_level:
        parts.append(f"--log-level {log_level}")
    parts.append("--disable-payment-verification")
    if testnet:
        parts.append("--network-mode testnet")
    return " ".join(parts)


def _build_unit_file(exec_start: str) -> str:
    """Build the systemd unit file content."""
    return f"""\
[Unit]
Description=Saorsa Genesis Node
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


class SaorsaGenesisNodeProvisioner:
    """Provisions the genesis node on a remote host using Pyinfra."""

    def __init__(
        self,
        ip: str,
        ssh_key_path: str = "~/.ssh/id_rsa",
        port: int | None = None,
        ip_version: str = "ipv4",
        log_level: str | None = None,
        testnet: bool = False,
        console: Console | None = None,
    ):
        self.ip = ip
        self.ssh_key_path = ssh_key_path
        self.port = port
        self.ip_version = ip_version
        self.log_level = log_level
        self.testnet = testnet
        self.console = console or Console()

    def execute(self) -> None:
        """Download the saorsa-node binary, install it, and start the genesis service."""
        self.console.print("Fetching latest release from GitHub...")
        download_url = _get_latest_release_url()
        self.console.print(f"  Release URL: {download_url}")

        exec_start = _build_exec_start(
            port=self.port,
            ip_version=self.ip_version,
            log_level=self.log_level,
            testnet=self.testnet,
        )
        unit_content = _build_unit_file(exec_start)

        self.console.print(f"Connecting to {self.ip} as root...")
        inventory = Inventory(
            (
                [
                    (
                        self.ip,
                        {"ssh_user": "root", "ssh_key": self.ssh_key_path},
                    ),
                ],
                {},
            ),
        )
        state = State(inventory=inventory, config=Config())
        connect_all(state)

        try:
            self.console.print("Downloading and installing saorsa-node binary...")
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

            self.console.print(f"Writing systemd unit file to {UNIT_FILE_PATH}...")
            self.console.print(f"  ExecStart: {exec_start}")
            add_op(
                state,
                files.put,
                name="Write systemd unit file",
                src=StringIO(unit_content),
                dest=UNIT_FILE_PATH,
                mode="644",
                add_deploy_dir=False,
            )

            self.console.print("Reloading systemd daemon...")
            add_op(
                state,
                systemd.daemon_reload,
                name="Reload systemd daemon",
            )

            self.console.print(f"Enabling and starting {SERVICE_NAME} service...")
            add_op(
                state,
                systemd.service,
                name="Enable and start genesis node service",
                service=SERVICE_NAME,
                running=True,
                enabled=True,
            )

            run_ops(state)
        finally:
            disconnect_all(state)
