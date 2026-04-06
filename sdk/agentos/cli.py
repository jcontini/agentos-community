"""agent-sdk CLI — guide, validate, new-skill, shapes."""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(prog="agent-sdk", description="agentOS Skill Development Kit")
    sub = parser.add_subparsers(dest="command")

    # guide
    sub.add_parser("guide", help="Print the skill development guide")

    # validate
    p_val = sub.add_parser("validate", help="Validate a skill directory")
    p_val.add_argument("dir", nargs="?", default=".", help="Skill directory to validate (default: current dir)")
    p_val.add_argument("--all", action="store_true", help="Validate all skills in parent directory")

    # new-skill
    p_new = sub.add_parser("new-skill", help="Scaffold a new skill")
    p_new.add_argument("name", help="Skill name (e.g. my-meetup-skill)")
    p_new.add_argument("--shape", default=None, help="Return shape (e.g. event, product)")

    # shapes
    p_shapes = sub.add_parser("shapes", help="List or inspect shapes")
    p_shapes.add_argument("name", nargs="?", help="Shape name to inspect")

    args = parser.parse_args()

    if args.command == "guide":
        from agentos.guide import print_guide
        print_guide()
    elif args.command == "validate":
        from agentos.validate import run_validate
        run_validate(args.dir, validate_all=args.all)
    elif args.command == "new-skill":
        from agentos.scaffold import run_new_skill
        run_new_skill(args.name, args.shape)
    elif args.command == "shapes":
        from agentos.shape_cli import run_shapes
        run_shapes(args.name)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
