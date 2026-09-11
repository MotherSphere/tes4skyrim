"""TES4 export text -> a binary Skyrim SE plugin.

Layout:

- base/         readers, the writer, and the tables every domain shares
- generated/    tool output; never hand-edited (see its README)
- record_types/ one converter per TES4 record signature
- dialogue/     DIAL/INFO/QUST, speak-as voices, conversations
- packages/     TES4 PACK -> TES5 package templates
- actors/       races, outfits, faces, hair, idles, footsteps
- overrides/    plugins that have TES4 masters
- navmesh/      PGRD -> NAVM generation
- registry.py   which converter handles which signature
- import_main   the orchestrator

Deliberately EMPTY of imports. Importing any leaf module runs this one, so a
re-export here would drag all 17 converters -- and their `core` dependency --
into a tool that only wanted a single reader.

See: docs/reference/record_mapping.md#dispatch-table-membership
"""
