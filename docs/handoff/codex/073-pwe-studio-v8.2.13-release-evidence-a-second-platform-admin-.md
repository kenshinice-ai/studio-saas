# PWE Studio v8.2.13 — release evidence, a second platform admin, and a retracted finding (2026-08-02)

## A correction first: the "16 exposed accounts" finding was wrong

The previous handoff carried a SECURITY section claiming 16 production accounts
still accepted the seed password `admin123456`, including the only platform
super-admin. **That was a bug in the checking script, not a finding.** It has
been removed from this document and from memory.

```python
