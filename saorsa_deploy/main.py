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
        "--node-count",
        type=int,
        required=True,
        help="Number of nodes per VM",
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
    elif args.command == "destroy":
        from saorsa_deploy.cmd.destroy import cmd_destroy

        cmd_destroy(args)


if __name__ == "__main__":
    main()
