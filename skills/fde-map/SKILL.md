---
name: fde-map
description: A feature's product map from its code: screens, API calls, handlers, business rules, events, columns written and tables read. Use when asked what a screen does under the hood, where a value comes from, or what a change touches.
---

# fde-map

A feature's map is `docs/map/<slug>.md`, a reference beside the specs.
The top is for people: by screen, the business-rule catalog, events,
who writes and reads each table. The bottom is the edge list
(`source  relation  target  [provenance]`) for agents and graph tools.

```bash
python3 bin/fde/productmap.py --write               # every feature
python3 bin/fde/productmap.py --feature <slug> --write
python3 bin/fde/productmap.py --check               # exit 1 when out of date
python3 bin/fde/productmap.py --format json         # nodes + edges
```

## First use: write the conventions, by reading the code

The kernel knows no project. `docs/map/conventions.toml` tells the
generator where this project keeps each thing. Read the code and fill
it; never guess a field you did not see.

| section | find in the code |
|---|---|
| `[frontend]` | `source_root`; the file with the `<Route>` tree (`routes_file`); the modules that export an API client object (`client_glob`); a helper that builds a base path (`path_base_helper`) |
| `[backend]` | the handlers' module-level route table name (`route_table`); a shared-module directory whose copies live beside handlers (`shared_dir`); a regex for table names (`table_pattern`, one group); a SQL tag comment if the project tags statements (`sql_tag`); `migrations_glob` |
| `[rules]` | the function a handler calls to refuse (`refusal_calls`, plus any wrapper that passes the code on); the dicts that hold each code's HTTP status and user message (`catalogs`, with `messages_from` when the message is a vocabulary constant); guard name prefixes (`guard_prefixes`); protocol codes to leave out of the rule catalog (`protocol_codes`) |
| `[events]` | functions that emit a named event (`emit_calls`) |
| `[[feature]]` | one per feature: `slug`, `name`, `route_prefix`, `feature_dir`, `handler_glob` |

Then run it and **measure before trusting it**: pick five operations,
follow each by hand from screen to table, and check the map has every
link. A missing link is a convention to fix, not a map to edit.

## What the map shows, and its limits

- A column written through SQL built at run time shows as `{?}`: the
  link exists, its columns are not known statically.
- Adapters shipped: a JSX `<Route>` tree with exported API client
  objects; Python handlers behind a route table, with SQL in strings
  and migrations. Another stack needs another adapter.
- Business rules are the refusal codes a handler or its guards can
  raise; the message is what the user reads.

## The declared block

Between the `FDE-MAP:DECLARED` markers, write what code cannot show:
intent, external systems, known gaps. It is carried over on every
regeneration; everything else is rewritten.

## Using it

- A demand spec cites map nodes (`column:<table>.<col>`,
  `rule:<CODE>`) instead of describing the feature again.
- Before planning slices (kernel ADR-0024), two slices that write the
  same table or handler share a seam.
- A review of a diff that touches a column reads which screens reach it.

## Exporting it

```bash
python3 bin/fde/mapexport.py --export mermaid [--feature <slug>]   # one flowchart per screen
python3 bin/fde/mapexport.py --export mermaid --screen /billing     # one screen
python3 bin/fde/mapexport.py --export jgf|graphml|dot > map.<ext>   # JSON Graph Format, Gephi/yEd/Cytoscape, Graphviz
```

The whole graph in one Mermaid chart is unreadable, so Mermaid is split
by screen. `--input <file>` (or `-`) reads a `productmap.py --format json`
instead of building the map again. The `MAP` gate warns when a map no
longer matches the code; it never fails yet.
