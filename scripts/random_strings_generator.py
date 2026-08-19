#!/usr/bin/env python3

import argparse
import secrets
import string


def generate_random_string(length: int) -> str:
    if length < 32:
        raise ValueError("The length must be at least 32 characters.")

    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a random string of at least 32 characters."
    )
    parser.add_argument(
        "length",
        nargs="?",
        type=int,
        default=64,
        help="Number of characters to generate (default: 64)",
    )
    args = parser.parse_args()

    try:
        print(generate_random_string(args.length))
    except ValueError as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
