cycle: C-<n>

<!-- kernel ADR-0019 rule 11. The board is the record (I7), not the conversation.
One line per event. A demand's files are its plan row (`files`); which
demands run together is `status.py --waves`. A demand that needs a file
outside its row posts `claim widened`; if another demand holds it, it
posts blocked-on and waits for its merge. A decision that changes an ADR or a
criterion is a replan, not a board line. -->

`<date> <demand> <claim|proposes|blocked-on|decided> <what>`

- YYYY-MM-DD C-<n> decided plan signed off
- YYYY-MM-DD DEM-<n> claim widened <files outside its plan row>
- YYYY-MM-DD DEM-<n> decided merged <sha>; review `reviews/DEM-<n>/findings.toml`
