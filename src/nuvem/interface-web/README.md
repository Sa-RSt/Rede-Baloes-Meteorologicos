# interface-web

Flask + SQLAlchemy web interface for the meteorological balloon network. It
reads the `Baloes` and `Leituras` tables from `sqlite.db` and exposes one table
page per balloon/sensor pair:

```
/                     # all balloons, shown as responsive cards
/<balao_id>           # all sensor types of one balloon, shown as cards
/<balao_id>/<sensor>  # readings of one sensor, ordered by data_hora
```

Readings are always ordered by `data_hora` descending (most recent first).

## Database

The application expects this SQLite schema:

```sql
CREATE TABLE IF NOT EXISTS Baloes (
    id INTEGER PRIMARY KEY,
    nome VARCHAR(50) NOT NULL,
    criado_em DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS Leituras (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    balao_id INTEGER NOT NULL,
    sensor VARCHAR(50) NOT NULL,
    leitura NUMERIC NOT NULL,
    data_hora DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (balao_id) REFERENCES Baloes(id)
);

CREATE INDEX IF NOT EXISTS idx_leituras_balao ON Leituras(balao_id);
CREATE INDEX IF NOT EXISTS idx_leituras_data ON Leituras(data_hora);
```

By default the database file is `sqlite.db` next to `pyproject.toml`. Set
`DATABASE_URL` to use a different database, for example:

```sh
DATABASE_URL=sqlite:////absolute/path/to/sqlite.db uv run interface-web
```

If the file or the tables do not exist, they are created automatically on
startup. They can also be created explicitly with:

```sh
uv run flask --app interface_web init-db
```

## Generating random test data

The `seed-db` script creates a new database populated with random balloons and
readings for every sensor type. By default it writes `sqlite.db` next to
`pyproject.toml`:

```sh
uv run seed-db --force
```

Options:

```text
--database PATH      output SQLite file (default: ./sqlite.db)
--baloes N           number of balloons, IDs 1..N (default: 4)
--readings N         readings per balloon/sensor pair (default: 100)
--days N             time span covered by the readings (default: 7)
--seed N             random seed for reproducible data
--force              overwrite the database if it already exists
```

`--stations` is accepted as a backward-compatible alias for `--baloes`.

Example with two balloons and 50 readings per pair:

```sh
uv run seed-db --force --baloes 2 --readings 50 --days 3 --seed 42
```

## Running

```sh
uv run interface-web
```

Then open <http://127.0.0.1:5000/>. The index lists every balloon as a card;
select a balloon to see its sensor types as cards.

Environment variables:

- `DATABASE_URL` — SQLAlchemy database URL (default: the local `sqlite.db`).
- `HOST` — bind address (default: `127.0.0.1`).
- `PORT` — HTTP port (default: `5000`).
- `FLASK_DEBUG=1` — enable the Flask debugger.

## UI

The interface uses Bootstrap 5 and jQuery. The header contains:

- a tree menu of every balloon (expandable) with its sensor types as leaves;
- links from each balloon to its card page;
- quick links to every sensor type of the balloon currently being viewed.

The index page shows every balloon in a responsive row of cards. Each balloon
page shows that balloon's sensor types in the same card layout. The readings
table shows the data/hora, leitura, sensor, and balloon for each row.

## Tests

```sh
uv run pytest
```

The tests use isolated temporary SQLite databases and cover the schema and
indexes, timestamp ordering, every balloon/sensor page, the tree/shortcut
navigation, Unicode sensor names, and the 404 pages.
