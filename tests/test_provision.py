from unittest.mock import MagicMock, patch

import pytest

from saorsa_deploy.provisioning.node import (
    SaorsaNodeProvisioner,
    _build_node_exec_start,
    _build_node_unit_file,
)


class TestBuildNodeExecStart:
    def test_includes_bootstrap_address(self):
        result = _build_node_exec_start("10.0.0.1", 5000)
        assert "--bootstrap 10.0.0.1:5000" in result

    def test_includes_port_when_specified(self):
        result = _build_node_exec_start("10.0.0.1", 5000, port=6000)
        assert "--port 6000" in result

    def test_no_port_when_not_specified(self):
        result = _build_node_exec_start("10.0.0.1", 5000)
        assert "--port" not in result

    def test_default_ip_version_is_ipv4(self):
        result = _build_node_exec_start("10.0.0.1", 5000)
        assert "--ip-version ipv4" in result

    def test_ip_version_can_be_overridden(self):
        result = _build_node_exec_start("10.0.0.1", 5000, ip_version="ipv6")
        assert "--ip-version ipv6" in result
        assert "--ip-version ipv4" not in result

    def test_includes_log_level(self):
        result = _build_node_exec_start("10.0.0.1", 5000, log_level="debug")
        assert "--log-level debug" in result

    def test_includes_testnet_flag(self):
        result = _build_node_exec_start("10.0.0.1", 5000, testnet=True)
        assert "--network-mode testnet" in result

    def test_no_network_mode_when_not_testnet(self):
        result = _build_node_exec_start("10.0.0.1", 5000, testnet=False)
        assert "--network-mode" not in result

    def test_always_includes_disable_payment_verification(self):
        result = _build_node_exec_start("10.0.0.1", 5000)
        assert "--disable-payment-verification" in result

    def test_all_flags(self):
        result = _build_node_exec_start(
            "10.0.0.1", 5000, port=6000, ip_version="v4", log_level="info", testnet=True
        )
        assert "--bootstrap 10.0.0.1:5000" in result
        assert "--port 6000" in result
        assert "--ip-version v4" in result
        assert "--log-level info" in result
        assert "--disable-payment-verification" in result
        assert "--network-mode testnet" in result


class TestBuildNodeUnitFile:
    def test_contains_service_name_in_description(self):
        unit = _build_node_unit_file("saorsa-node-1", "/usr/local/bin/saorsa-node --port 5000")
        assert "Description=Saorsa Node (saorsa-node-1)" in unit

    def test_contains_exec_start(self):
        exec_start = "/usr/local/bin/saorsa-node --bootstrap 10.0.0.1:5000 --port 6000"
        unit = _build_node_unit_file("saorsa-node-1", exec_start)
        assert f"ExecStart={exec_start}" in unit

    def test_contains_service_sections(self):
        unit = _build_node_unit_file("saorsa-node-1", "/usr/local/bin/saorsa-node")
        assert "[Service]" in unit
        assert "[Unit]" in unit
        assert "[Install]" in unit
        assert "Restart=always" in unit
        assert "WantedBy=multi-user.target" in unit


class TestSaorsaNodeProvisioner:
    def test_init_defaults(self):
        provisioner = SaorsaNodeProvisioner(
            host_ips=["10.0.0.1", "10.0.0.2"],
            bootstrap_ip="10.0.0.100",
            bootstrap_port=5000,
        )
        assert provisioner.host_ips == ["10.0.0.1", "10.0.0.2"]
        assert provisioner.bootstrap_ip == "10.0.0.100"
        assert provisioner.bootstrap_port == 5000
        assert provisioner.ssh_key_path == "~/.ssh/id_rsa"
        assert provisioner.node_count == 1
        assert provisioner.initial_port is None
        assert provisioner.ip_version == "ipv4"
        assert provisioner.log_level is None
        assert provisioner.testnet is False

    def test_init_all_params(self):
        provisioner = SaorsaNodeProvisioner(
            host_ips=["10.0.0.1"],
            bootstrap_ip="10.0.0.100",
            bootstrap_port=5000,
            ssh_key_path="/tmp/key",
            node_count=3,
            initial_port=6000,
            ip_version="v4",
            log_level="debug",
            testnet=True,
        )
        assert provisioner.ssh_key_path == "/tmp/key"
        assert provisioner.node_count == 3
        assert provisioner.initial_port == 6000
        assert provisioner.ip_version == "v4"
        assert provisioner.log_level == "debug"
        assert provisioner.testnet is True

    @patch("saorsa_deploy.provisioning.node.disconnect_all")
    @patch("saorsa_deploy.provisioning.node.run_ops")
    @patch("saorsa_deploy.provisioning.node.add_op")
    @patch("saorsa_deploy.provisioning.node.connect_all")
    @patch("saorsa_deploy.provisioning.node.State")
    @patch("saorsa_deploy.provisioning.node.Inventory")
    @patch("saorsa_deploy.provisioning.node._get_latest_release_url")
    def test_execute_calls_pyinfra_operations(
        self,
        mock_release_url,
        _mock_inventory,
        mock_state,
        mock_connect,
        mock_add_op,
        mock_run_ops,
        mock_disconnect,
    ):
        mock_release_url.return_value = "https://github.com/download/v1.0.0/asset.tar.gz"
        mock_state_instance = MagicMock()
        mock_state_instance.failed_hosts = set()
        mock_state.return_value = mock_state_instance

        provisioner = SaorsaNodeProvisioner(
            host_ips=["10.0.0.1"],
            bootstrap_ip="10.0.0.100",
            bootstrap_port=5000,
            node_count=2,
        )
        provisioner.execute()

        mock_connect.assert_called_once()
        # 1 download + 1 write-units + 1 enable-and-start = 3
        assert mock_add_op.call_count == 3
        mock_run_ops.assert_called_once()
        mock_disconnect.assert_called_once()

    @patch("saorsa_deploy.provisioning.node.disconnect_all")
    @patch("saorsa_deploy.provisioning.node.run_ops")
    @patch("saorsa_deploy.provisioning.node.add_op")
    @patch("saorsa_deploy.provisioning.node.connect_all")
    @patch("saorsa_deploy.provisioning.node.State")
    @patch("saorsa_deploy.provisioning.node.Inventory")
    @patch("saorsa_deploy.provisioning.node._get_latest_release_url")
    def test_execute_disconnects_on_error(
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

        provisioner = SaorsaNodeProvisioner(
            host_ips=["10.0.0.1"],
            bootstrap_ip="10.0.0.100",
            bootstrap_port=5000,
        )
        with pytest.raises(RuntimeError, match="connection failed"):
            provisioner.execute()

        mock_disconnect.assert_called_once()

    @patch("saorsa_deploy.provisioning.node.disconnect_all")
    @patch("saorsa_deploy.provisioning.node.run_ops")
    @patch("saorsa_deploy.provisioning.node.add_op")
    @patch("saorsa_deploy.provisioning.node.connect_all")
    @patch("saorsa_deploy.provisioning.node.State")
    @patch("saorsa_deploy.provisioning.node.Inventory")
    @patch("saorsa_deploy.provisioning.node._get_latest_release_url")
    def test_execute_creates_inventory_with_all_hosts(
        self,
        mock_release_url,
        mock_inventory,
        mock_state,
        _mock_connect,
        _mock_add_op,
        _mock_run_ops,
        _mock_disconnect,
    ):
        mock_release_url.return_value = "https://github.com/download/v1.0.0/asset.tar.gz"
        mock_state_instance = MagicMock()
        mock_state_instance.failed_hosts = set()
        mock_state.return_value = mock_state_instance

        provisioner = SaorsaNodeProvisioner(
            host_ips=["10.0.0.1", "10.0.0.2", "10.0.0.3"],
            bootstrap_ip="10.0.0.100",
            bootstrap_port=5000,
            ssh_key_path="/tmp/mykey",
        )
        provisioner.execute()

        inventory_call = mock_inventory.call_args
        hosts_data = inventory_call[0][0][0]
        assert len(hosts_data) == 3
        assert hosts_data[0][0] == "10.0.0.1"
        assert hosts_data[0][1]["ssh_user"] == "root"
        assert hosts_data[0][1]["ssh_key"] == "/tmp/mykey"
        assert hosts_data[1][0] == "10.0.0.2"
        assert hosts_data[2][0] == "10.0.0.3"

    @patch("saorsa_deploy.provisioning.node.disconnect_all")
    @patch("saorsa_deploy.provisioning.node.run_ops")
    @patch("saorsa_deploy.provisioning.node.add_op")
    @patch("saorsa_deploy.provisioning.node.connect_all")
    @patch("saorsa_deploy.provisioning.node.State")
    @patch("saorsa_deploy.provisioning.node.Inventory")
    @patch("saorsa_deploy.provisioning.node._get_latest_release_url")
    def test_execute_creates_correct_service_count(
        self,
        mock_release_url,
        _mock_inventory,
        mock_state,
        _mock_connect,
        mock_add_op,
        _mock_run_ops,
        _mock_disconnect,
    ):
        mock_release_url.return_value = "https://github.com/download/v1.0.0/asset.tar.gz"
        mock_state_instance = MagicMock()
        mock_state_instance.failed_hosts = set()
        mock_state.return_value = mock_state_instance

        provisioner = SaorsaNodeProvisioner(
            host_ips=["10.0.0.1"],
            bootstrap_ip="10.0.0.100",
            bootstrap_port=5000,
            node_count=3,
        )
        provisioner.execute()

        # 1 download + 1 write-units + 1 enable-and-start = 3
        assert mock_add_op.call_count == 3

    @patch("saorsa_deploy.provisioning.node.disconnect_all")
    @patch("saorsa_deploy.provisioning.node.run_ops")
    @patch("saorsa_deploy.provisioning.node.add_op")
    @patch("saorsa_deploy.provisioning.node.connect_all")
    @patch("saorsa_deploy.provisioning.node.State")
    @patch("saorsa_deploy.provisioning.node.Inventory")
    @patch("saorsa_deploy.provisioning.node._get_latest_release_url")
    def test_execute_raises_when_hosts_fail(
        self,
        mock_release_url,
        _mock_inventory,
        mock_state,
        _mock_connect,
        _mock_add_op,
        _mock_run_ops,
        _mock_disconnect,
    ):
        mock_release_url.return_value = "https://github.com/download/v1.0.0/asset.tar.gz"
        failed_host = MagicMock()
        failed_host.name = "10.0.0.1"
        mock_state_instance = MagicMock()
        mock_state_instance.failed_hosts = {failed_host}
        mock_state.return_value = mock_state_instance

        provisioner = SaorsaNodeProvisioner(
            host_ips=["10.0.0.1"],
            bootstrap_ip="10.0.0.100",
            bootstrap_port=5000,
        )
        with pytest.raises(RuntimeError, match="1 host\\(s\\) failed provisioning"):
            provisioner.execute()
