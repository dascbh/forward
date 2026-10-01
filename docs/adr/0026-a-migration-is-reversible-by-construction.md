# ADR-0026 — A migration is reversible by construction

date: 2026-09-30
status: accepted (owner, direct, 2026-09-30)
builds on: ADR-0019 rule 5 (deploy order infra-expand → back → front →
infra-contract), ADR-0025 (declared deploy commands run without a prompt)

## Context

The owner's goal is to protect executions without blocking them. A client
cycle's deploy carried a migration that changed a key in place. The code
from before the cycle could not run after it, and the new code could not
run before it. Its only safety net was a database snapshot, which serves
only a disaster: restoring it builds a new cluster and loses every write
made after it. The same client's migration runner applies one statement
per call, outside a transaction, so a failure mid-file leaves the schema
half changed. It keeps no down migrations.

Mature practice (expand/contract, parallel change) makes rollback a
property of the design, not a script written under pressure. Hand-written
down migrations are seldom tested and often lose data. A rollback that
was rehearsed is a fact; one that was not is a hope.

## Decision

1. **Expand, then contract, in separate cycles.** A deploy changes the
   schema only in ways the code it replaces still runs on: add a table, a
   nullable column, a new key beside the old one, then backfill and
   dual-write. Drop, rename, type change and key swap are the contract,
   planned in a later cycle after a validation window. Rolling back a
   deploy is then rolling back its code, and no data is lost. `fde-spec`
   plans every destructive schema change this way.
2. **Every migration step declares its protection** in `deploy.md`:
   - `Migration: expand | contract | data`;
   - `Checkpoint:` the command that records a restore point right before
     it (snapshot or point-in-time marker), run by the deploy and never
     waiting on anyone;
   - `Rehearsal:` the command that applies it to a clone of production,
     runs the checks and the rollback, and confirms the previous code
     still runs, with the path of its evidence;
   - `Rollback: code` (expand), `down <file>` (rehearsed), or
     `forward-fix` (data already changed: a new migration fixes it).

   The checkpoint and rehearsal commands are listed under `## Commands`,
   so they run without a prompt (ADR-0025).
3. **A migration file is atomic.** It runs in one transaction, so a
   failure leaves nothing half applied. A statement that cannot run in a
   transaction (`CREATE INDEX CONCURRENTLY`) is idempotent and resumable,
   and the step says so.
4. **Nothing here blocks.** Promotion records the rehearsal evidence. A
   missing field or missing evidence is a `MIGRATION` ⚠ warning, never a
   failure. The owner's sign-off still decides; the plan makes the
   rollback real.

5. **The sync builds it, the owner does not coordinate it.** On every
   sync, reconcile fills each live migration step's fields itself and,
   where the project lacks a rehearsal tool or an atomic runner, builds
   them in the project as a direct-lane change. What cannot be built is
   a reported limit; only a replan reaches the owner (owner direction,
   2026-09-30: "não quero ficar tendo que coordenar").

## Alternatives rejected

- **A gate that fails a deploy without a down migration.** It would block
  executions, which the owner ruled out. It would also reward untested
  down scripts.
- **Down migrations as the rollback.** They are written after the fact,
  rarely run, and lossy for data changes. They count only when rehearsed.
- **Snapshot as the rollback.** It restores a new cluster and drops every
  write after it. It stays as the disaster net (Checkpoint), not the plan.

## Consequences

- A cycle with a destructive schema change becomes two cycles: expand, and
  later contract. That is the price of a rollback that always exists.
- The client's own tooling must provide transactional application and a
  clone to rehearse on. The kernel asks for them in the plan and warns
  when they are missing; it carries no client code.
