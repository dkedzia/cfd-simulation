from db.migrate import migrate
from db.models.ping import Ping


def main() -> None:
    versions = migrate()
    if versions:
        print(f"Applied migrations: {', '.join(versions)}")
    else:
        print("Migrations up to date.")

    ping = Ping(message="sqlite smoke test").save()
    print(f"Saved Ping id={ping.id} message={ping.message!r} created_at={ping.created_at}")

    loaded = Ping.find(ping.id)
    if loaded is None:
        raise SystemExit("Ping.find failed")
    print(f"Loaded Ping id={loaded.id} message={loaded.message!r}")


if __name__ == "__main__":
    main()
