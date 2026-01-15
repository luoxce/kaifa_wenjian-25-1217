"""Apply database migrations."""

from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from alpha_arena.db.migrate import migrate


def main() -> None:
    migrate()
    print("Database migrations applied.")


if __name__ == "__main__":
    main()
