import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="saorsa-deploy",
        description="Deploy testnets for saorsa-node using Terraform and Pyinfra",
    )
    subparsers = parser.add_subparsers(dest="command")

    infra_parser = subparsers.add_parser("infra", help="Manage testnet infrastructure")
    infra_parser.add_argument(
        "--attached-volume-size",
        type=int,
        default=20,
        help="Size of attached volume in GB (default: 20)",
    )
    infra_parser.add_argument(
        "--name",
        type=str,
        required=True,
        help="Deployment name (used as prefix in VM names, e.g. DEV-01)",
    )
    infra_parser.add_argument(
        "--region-counts",
        type=str,
        default="3",
        help="Comma-separated region counts per provider (default: 3)",
    )
    infra_parser.add_argument(
        "--testnet",
        action="store_true",
        help="Run in testnet mode (Digital Ocean only, lon1 region)",
    )
    infra_parser.add_argument(
        "--vm-count",
        type=int,
        required=True,
        help="Number of VMs per provider per region",
    )

    provision_genesis_parser = subparsers.add_parser(
        "provision-genesis", help="Provision the genesis node"
    )
    provision_genesis_parser.add_argument(
        "--ip-version",
        type=str,
        choices=["v4", "v6"],
        help="IP version the node will run with (v4 or v6)",
    )
    provision_genesis_parser.add_argument(
        "--log-level",
        type=str,
        help="Logging level the node will run with",
    )
    provision_genesis_parser.add_argument(
        "--name",
        type=str,
        required=True,
        help="Deployment name (must match the name used with infra command)",
    )
    provision_genesis_parser.add_argument(
        "--port",
        type=int,
        required=True,
        help="Port the genesis node will run with (required for bootstrap address)",
    )
    provision_genesis_parser.add_argument(
        "--ssh-key-path",
        type=str,
        default="~/.ssh/id_rsa",
        help="Path to SSH key for provisioning (default: ~/.ssh/id_rsa)",
    )
    provision_genesis_parser.add_argument(
        "--testnet",
        action="store_true",
        help="Run the node with the --testnet flag",
    )

    provision_parser = subparsers.add_parser("provision", help="Provision nodes on all VMs")
    provision_parser.add_argument(
        "--ip-version",
        type=str,
        choices=["v4", "v6"],
        help="IP version the nodes will run with (v4 or v6)",
    )
    provision_parser.add_argument(
        "--log-level",
        type=str,
        help="Logging level the nodes will run with",
    )
    provision_parser.add_argument(
        "--name",
        type=str,
        required=True,
        help="Deployment name (must match the name used with infra command)",
    )
    provision_parser.add_argument(
        "--node-count",
        type=int,
        required=True,
        help="Number of node services per VM",
    )
    provision_parser.add_argument(
        "--port",
        type=int,
        help="Beginning of a port range from PORT to PORT+N (omit for random ports)",
    )
    provision_parser.add_argument(
        "--region",
        type=str,
        help="Provision only VMs in this region (e.g., digitalocean/lon1)",
    )
    provision_parser.add_argument(
        "--ssh-key-path",
        type=str,
        default="~/.ssh/id_rsa",
        help="Path to SSH key for provisioning (default: ~/.ssh/id_rsa)",
    )
    provision_parser.add_argument(
        "--testnet",
        action="store_true",
        help="Run the nodes with the --testnet flag",
    )

    destroy_parser = subparsers.add_parser("destroy", help="Destroy testnet infrastructure")
    destroy_parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt",
    )
    destroy_parser.add_argument(
        "--name",
        type=str,
        required=True,
        help="Deployment name to destroy",
    )

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command == "infra":
        from saorsa_deploy.cmd.infra import cmd_infra

        cmd_infra(args)
    elif args.command == "provision-genesis":
        from saorsa_deploy.cmd.provision_genesis import cmd_provision_genesis

        cmd_provision_genesis(args)
    elif args.command == "provision":
        from saorsa_deploy.cmd.provision import cmd_provision

        cmd_provision(args)
    elif args.command == "destroy":
        from saorsa_deploy.cmd.destroy import cmd_destroy

        cmd_destroy(args)


if __name__ == "__main__":
    main()
