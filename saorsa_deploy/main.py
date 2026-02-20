import argparse
import sys


def cmd_infra(args):
    print("infra command not yet implemented")


def main():
    parser = argparse.ArgumentParser(
        prog="saorsa-deploy",
        description="Deploy testnets for saorsa-node using Terraform and Pyinfra",
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("infra", help="Manage testnet infrastructure")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command == "infra":
        cmd_infra(args)


if __name__ == "__main__":
    main()
