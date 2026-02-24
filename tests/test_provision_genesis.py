from unittest.mock import MagicMock, patch

import pytest

from saorsa_deploy.provisioning.genesis import (
    BINARY_INSTALL_PATH,
    SERVICE_NAME,
    SaorsaGenesisNodeProvisioner,
    _build_exec_start,
    _build_unit_file,
    _get_latest_release_url,
)


class TestBuildExecStart:
    def test_minimal_flags(self):
        result = _build_exec_start()
        assert result == f"{BINARY_INSTALL_PATH} --ip-version ipv4 --disable-payment-verification"

    def test_all_flags(self):
        result = _build_exec_start(port=10000, ip_version="ipv4", log_level="debug", testnet=True)
        assert "--port 10000" in result
        assert "--ip-version ipv4" in result
        assert "--log-level debug" in result
        assert "--disable-payment-verification" in result
        assert "--network-mode testnet" in result

    def test_port_only(self):
        result = _build_exec_start(port=5000)
        assert "--port 5000" in result
        assert "--ip-version ipv4" in result
        assert "--log-level" not in result
        assert "--network-mode" not in result

    def test_default_ip_version_is_ipv4(self):
        result = _build_exec_start()
        assert "--ip-version ipv4" in result

    def test_ip_version_can_be_overridden(self):
        result = _build_exec_start(ip_version="ipv6")
        assert "--ip-version ipv6" in result
        assert "--ip-version ipv4" not in result

    def test_testnet_flag(self):
        result = _build_exec_start(testnet=True)
        assert result.endswith("--network-mode testnet")

    def test_no_network_mode_when_not_testnet(self):
        result = _build_exec_start(testnet=False)
        assert "--network-mode" not in result

    def test_disable_payment_verification_always_present(self):
        result = _build_exec_start()
        assert "--disable-payment-verification" in result


class TestBuildUnitFile:
    def test_contains_exec_start(self):
        exec_start = "/usr/local/bin/saorsa-node --port 10000"
        unit = _build_unit_file(exec_start)
        assert f"ExecStart={exec_start}" in unit

    def test_contains_service_section(self):
        unit = _build_unit_file("/usr/local/bin/saorsa-node")
        assert "[Service]" in unit
        assert "[Unit]" in unit
        assert "[Install]" in unit
        assert "Restart=always" in unit
        assert "WantedBy=multi-user.target" in unit


class TestGetLatestReleaseUrl:
    @patch("saorsa_deploy.provisioning.genesis.requests.get")
    def test_returns_download_url(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "assets": [
                {
                    "name": "saorsa-node-cli-linux-x64.tar.gz",
                    "browser_download_url": "https://github.com/download/v1.0.0/asset.tar.gz",
                },
            ],
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        url = _get_latest_release_url()
        assert url == "https://github.com/download/v1.0.0/asset.tar.gz"

    @patch("saorsa_deploy.provisioning.genesis.requests.get")
    def test_raises_when_asset_not_found(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "assets": [{"name": "other-asset.tar.gz", "browser_download_url": "https://x"}],
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        with pytest.raises(RuntimeError, match="Could not find asset"):
            _get_latest_release_url()

    @patch("saorsa_deploy.provisioning.genesis.requests.get")
    def test_raises_when_no_assets(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"assets": []}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        with pytest.raises(RuntimeError, match="Could not find asset"):
            _get_latest_release_url()


class TestSaorsaGenesisNodeProvisioner:
    def test_init_defaults(self):
        node = SaorsaGenesisNodeProvisioner(ip="10.0.0.1")
        assert node.ip == "10.0.0.1"
        assert node.ssh_key_path == "~/.ssh/id_rsa"
        assert node.port is None
        assert node.ip_version == "ipv4"
        assert node.log_level is None
        assert node.testnet is False

    def test_init_all_params(self):
        node = SaorsaGenesisNodeProvisioner(
            ip="10.0.0.1",
            ssh_key_path="/tmp/key",
            port=10000,
            ip_version="ipv4",
            log_level="debug",
            testnet=True,
        )
        assert node.ip == "10.0.0.1"
        assert node.ssh_key_path == "/tmp/key"
        assert node.port == 10000
        assert node.ip_version == "ipv4"
        assert node.log_level == "debug"
        assert node.testnet is True

    @patch("saorsa_deploy.provisioning.genesis.disconnect_all")
    @patch("saorsa_deploy.provisioning.genesis.run_ops")
    @patch("saorsa_deploy.provisioning.genesis.add_op")
    @patch("saorsa_deploy.provisioning.genesis.connect_all")
    @patch("saorsa_deploy.provisioning.genesis.State")
    @patch("saorsa_deploy.provisioning.genesis.Inventory")
    @patch("saorsa_deploy.provisioning.genesis._get_latest_release_url")
    def test_provision_calls_pyinfra_operations(
        self,
        mock_release_url,
        _mock_inventory,
        _mock_state,
        mock_connect,
        mock_add_op,
        mock_run_ops,
        mock_disconnect,
    ):
        mock_release_url.return_value = "https://github.com/download/v1.0.0/asset.tar.gz"

        node = SaorsaGenesisNodeProvisioner(ip="10.0.0.1", port=10000, ip_version="ipv4")
        node.execute()

        mock_connect.assert_called_once()
        assert mock_add_op.call_count == 4
        mock_run_ops.assert_called_once()
        mock_disconnect.assert_called_once()

    @patch("saorsa_deploy.provisioning.genesis.disconnect_all")
    @patch("saorsa_deploy.provisioning.genesis.run_ops")
    @patch("saorsa_deploy.provisioning.genesis.add_op")
    @patch("saorsa_deploy.provisioning.genesis.connect_all")
    @patch("saorsa_deploy.provisioning.genesis.State")
    @patch("saorsa_deploy.provisioning.genesis.Inventory")
    @patch("saorsa_deploy.provisioning.genesis._get_latest_release_url")
    def test_provision_disconnects_on_error(
        self,
        mock_release_url,
        _mock_inventory,
        _mock_state,
        _mock_connect,
        _mock_add_op,
        mock_run_ops,
        mock_disconnect,
    ):
        mock_release_url.return_value = "https://github.com/download/v1.0.0/asset.tar.gz"
        mock_run_ops.side_effect = RuntimeError("connection failed")

        node = SaorsaGenesisNodeProvisioner(ip="10.0.0.1")
        with pytest.raises(RuntimeError, match="connection failed"):
            node.execute()

        mock_disconnect.assert_called_once()

    @patch("saorsa_deploy.provisioning.genesis.disconnect_all")
    @patch("saorsa_deploy.provisioning.genesis.run_ops")
    @patch("saorsa_deploy.provisioning.genesis.add_op")
    @patch("saorsa_deploy.provisioning.genesis.connect_all")
    @patch("saorsa_deploy.provisioning.genesis.State")
    @patch("saorsa_deploy.provisioning.genesis.Inventory")
    @patch("saorsa_deploy.provisioning.genesis._get_latest_release_url")
    def test_provision_creates_inventory_with_correct_host(
        self,
        mock_release_url,
        mock_inventory,
        _mock_state,
        _mock_connect,
        _mock_add_op,
        _mock_run_ops,
        _mock_disconnect,
    ):
        mock_release_url.return_value = "https://github.com/download/v1.0.0/asset.tar.gz"

        node = SaorsaGenesisNodeProvisioner(ip="192.168.1.100", ssh_key_path="/tmp/mykey")
        node.execute()

        inventory_call = mock_inventory.call_args
        hosts = inventory_call[0][0][0]
        host_tuple = hosts[0]
        assert host_tuple[0] == "192.168.1.100"
        assert host_tuple[1]["ssh_user"] == "root"
        assert host_tuple[1]["ssh_key"] == "/tmp/mykey"

    @patch("saorsa_deploy.provisioning.genesis.disconnect_all")
    @patch("saorsa_deploy.provisioning.genesis.run_ops")
    @patch("saorsa_deploy.provisioning.genesis.add_op")
    @patch("saorsa_deploy.provisioning.genesis.connect_all")
    @patch("saorsa_deploy.provisioning.genesis.State")
    @patch("saorsa_deploy.provisioning.genesis.Inventory")
    @patch("saorsa_deploy.provisioning.genesis._get_latest_release_url")
    def test_provision_writes_systemd_unit_with_service_name(
        self,
        mock_release_url,
        _mock_inventory,
        _mock_state,
        _mock_connect,
        mock_add_op,
        _mock_run_ops,
        _mock_disconnect,
    ):
        mock_release_url.return_value = "https://github.com/download/v1.0.0/asset.tar.gz"

        node = SaorsaGenesisNodeProvisioner(ip="10.0.0.1")
        node.execute()

        # The 4th add_op call should be for enabling/starting the service
        service_call = mock_add_op.call_args_list[3]
        assert service_call.kwargs.get("service") == SERVICE_NAME
        assert service_call.kwargs.get("running") is True
        assert service_call.kwargs.get("enabled") is True
