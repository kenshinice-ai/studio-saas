# PWE Studio — the welcome pack (2026-08-03)

`docs/customer/Welcome_Pack.md`: the handover email, both languages, ready to
copy. Four addresses, change-your-password first, the manual deep-linked to
the four sections a new studio needs in week one, the import templates, and
what the platform can and cannot do inside their data.

**It is deliberately two messages.** The welcome email carries links and no
secrets; the temporary password goes by a channel the studio already uses. An
email thread is forwarded, quoted and kept for years, and a credential in one
outlives every reason it existed. That is the only part of the pack written as
a rule rather than a suggestion, and it is asserted — a well-meaning
"PS — your password is…" fails a test.

`test_welcome_pack.py` resolves **every link in the template against the
running app** (27 of them). A renamed route now fails a test instead of a
customer's first click. It also checks the placeholders all look like
placeholders, that both languages stand alone, and that the pack never
describes the manual as gated — it is public, and saying otherwise would be a
claim we cannot keep.

Onboarding checklist Phase 2 now has two lines: send the pack, send the
password separately.

548 tests pass. Still not deployed.

---

