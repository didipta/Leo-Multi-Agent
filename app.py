from dotenv import load_dotenv

load_dotenv()

from leo.orchestrator import Leo, Quit  # noqa: E402

if __name__ == "__main__":
    try:
        Leo().session()
    except (Quit, KeyboardInterrupt):
        print("\nBye! Leo remembers your progress for next time.")
