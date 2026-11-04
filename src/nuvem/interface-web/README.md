# interface-web

Flask + SQLAlchemy web interface for the meteorological balloon network. It
reads the `readings` table from `sqlite.db` and exposes one table page per
station/sensor pair:

```
/                 # all stations, shown as responsive cards
/<station_id>     # all sensor types of one station, shown as cards
/<station_id>/<sensor_type>
```

Readings are always ordered by `timestamp` descending (most recent first).

## Database

The application expects a SQLite table with this shape:

```sql
CREATE TABLE readings (
    sensor_type TEXT    NOT NULL,
    value       INTEGER NOT NULL,  -- unsigned
    station_id  INTEGER NOT NULL,
    timestamp   DATETIME NOT NULL
);
```

By default the database file is `sqlite.db` next to `pyproject.toml`. Set
`DATABASE_URL` to use a different database, for example:

```sh
DATABASE_URL=sqlite:////absolute/path/to/sqlite.db uv run interface-web
```

If the file or the table does not exist, it is created automatically on
startup. It can also be created explicitly with:

```sh
uv run flask --app interface_web init-db
```

## Generating random test data

The `seed-db` script creates a new database populated with random readings for
every station and sensor type. By default it writes `sqlite.db` next to
`pyproject.toml`:

```sh
uv run seed-db --force
```

Options:

```text
--database PATH      output SQLite file (default: ./sqlite.db)
--stations N         number of stations, IDs 0..N-1 (default: 4)
--readings N         readings per station/sensor pair (default: 100)
--days N             time span covered by the readings (default: 7)
--seed N             random seed for reproducible data
--force              overwrite the database if it already exists
```

Example with two stations and 50 readings per pair:

```sh
uv run seed-db --force --stations 2 --readings 50 --days 3 --seed 42
```

## Running

```sh
uv run interface-web
```

Then open <http://127.0.0.1:5000/>. The index lists every station as a card;
select a station to see its sensor types as cards.

Environment variables:

- `DATABASE_URL` — SQLAlchemy database URL (default: the local `sqlite.db`).
- `HOST` — bind address (default: `127.0.0.1`).
- `PORT` — HTTP port (default: `5000`).
- `FLASK_DEBUG=1` — enable the Flask debugger.

## UI

The interface uses Bootstrap 5 and jQuery. The header contains:

- a tree menu of every station (expandable) with its sensor types as leaves;
- links from each station to its `/station_id` card page;
- quick links to every sensor type of the station currently being viewed.

The index page shows every station in a responsive row of cards. Each station
page shows that station's sensor types in the same card layout. The readings
table shows the timestamp, value, sensor type, and station for each row.

## Tests

```sh
uv run pytest
```

The tests use isolated temporary SQLite databases and cover the schema, the
timestamp ordering, every station/sensor page, the tree/shortcut navigation,
Unicode sensor names, and the 404 pages.
