# NExUS usability review — Nielsen's ten heuristics

Date: 2026-10-27. Branches: `arena/8a745538-project-nexus` (initial pass),
`arena/489156e3-project-nexus` (POST-only deletes and undo).

## What this document is

The system is now held to Jakob Nielsen's ten usability heuristics. This is the
review that was done against them, what changed because of it, and — the part
that matters more — what is still not good enough.

Every change below is in the interface, not in a plan. Where a heuristic is only
partly met, it says so instead of claiming the box is ticked.

The heuristics are the public ones; the wording of each heading is Nielsen's.

## 1. Visibility of system status

*The system should always keep users informed about what is going on.*

| Was | Now |
|---|---|
| Signing in on a slow connection looked like nothing had happened; the button stayed enabled, so it was pressed twice. | `form[data-nx-busy]` marks the form `aria-busy`, relabels the button from `data-nx-busy-label` ("Signing in…", "Creating account…", "Saving…"), and disables it once the request is on its way. If the page never leaves, the button comes back after 20 s instead of staying dead (`static/js/nexus-forms.js`). |
| A rejected sign-in only produced a toast, which fades. | The same message is rendered above the form as a persistent summary (`accounts/login.html`), and took the place of a `{% if error %}` branch that nothing ever filled — the inline box had been dead markup. |
| Nothing told the user their session was about to end. | Already handled before this round: an inactivity warning with a countdown, and the reason shown on the sign-in page ("Your session expired due to inactivity"). |
| A password being typed gave no feedback until submission. | Rules light up under the field as each is met, Caps Lock is called out, and the confirmation says when both entries match (`static/js/nexus-password.js`). |

Remaining gap: there is no progress indication *inside* a long wizard step
beyond the save button. Twenty steps of a proposal save one step at a time, and
the rail shows position, but a step that takes a while shows only the button.

## 2. Match between the system and the real world

*Speak the users' language, follow real-world conventions.*

| Was | Now |
|---|---|
| The database's words surfaced on screen: "Status: SUBMITTED_FOR_REVIEW" style labels, approval codes, and record IDs next to human titles. | List and detail screens use the label, not the code (`get_status_display()` and friends); the wizard, trackers and review screens address the user in the vocabulary the Extension Office uses — proposal, MOA, terminal report, monitoring. |
| Workflow overview pages used internal jargon without matching actual sequence. | Services presents the three workflow phases (Proposal, MOA, Implementation) and wizard steps in plain sentences in the exact order work happens. |
| "Login" / "Logout" | "Sign in" / "Sign out" — the words on the button now match the words in the page title and the side panel, which already said "Sign in". |

## 3. User control and freedom

*Users need a clearly marked emergency exit.*

Done in this round:

- **Every destructive action asks first, the same way.** Confirmation used to be
  `onsubmit="return confirm(…)"` in some screens, `onclick="return confirm(…)"`
  in others, and the JS string lived inside the template. It is now one
  attribute — `data-nx-confirm="…"` — on the form, the link, or the outside
  button, handled in one place (`static/js/nexus-forms.js`). The question is
  written in the template where the wording can be reviewed, and cancellation
  happens before the busy state, so a change of heart leaves the button exactly
  as it was.
- **Deleting a draft** already used an in-page dialog with Escape to close; it
  was kept, and is now the only place a styled dialog is used rather than a
  second competing pattern.
- Cancel links sit next to Save on the admin forms rather than only in the
  browser's back button.
- **A deletion can be undone.** Every administrative delete snapshots the record
  — and everything a cascade would take with it — into the user's session before
  the row goes (`accounts/deletion.py`). A bar at the bottom of the page then
  offers **Undo** for fifteen minutes, with a live countdown: a campus comes back
  with its colleges and departments, a process with its steps, an activity with
  its dates. The snapshot is written back with the original primary keys and
  timestamps, so nothing is left pointing at a record that no longer exists and
  the restored row does not claim to have been edited today.
- **Deleting is a POST, never a link.** `activity_delete`, `personnel_delete` and
  `process_delete` were the last three reached by an `<a href>`; they are
  `@require_POST` now and their list screens submit a small form instead. A
  prefetching browser or a link scanner can no longer delete anything. The undo
  and dismiss endpoints are POST-only too — an undo URL is not a bookmark.
- **The confirmation prompt is now reserved for deletions that cannot be undone**:
  campus/college/department cascades that may exceed the snapshot limit, template
  files (the file itself is not restored), and wizard steps. Everything the undo
  bar covers drops the prompt, so the common case is one click instead of two.
- An undo belongs to the session that made it: another admin, or the same admin
  after signing out, cannot use the token.

## 4. Consistency and standards

*Users should not have to wonder whether different words, situations, or actions mean the same thing.*

- One component contract (`static/css/nexus-components.css`): `.nx-btn--primary`,
  `.nx-btn--secondary`, `.nx-btn--danger`, one control height, one focus ring.
- One confirmation convention (above) instead of three.
- One password field, everywhere: the reveal toggle, the rules list and the
  Caps Lock warning come from `accounts.forms.password_widget_attrs()`, so no
  template has to remember them, and a password field added later cannot ship
  without them.
- One error summary (`accounts/templates/accounts/_form_errors.html`) used by
  registration, the two admin account forms and password reset.
- Sentence case for headings and buttons ("Sign in", "Create your account",
  "Save changes"), rather than a mix of Title Case and sentence case.
- The words "Login"/"Logout" were removed in favour of "Sign in"/"Sign out"
  everywhere in the chrome.

## 5. Error prevention

*Prevent problems before they occur.*

- Passwords are checked against the same rules on the client as on the server,
  while they are typed — not after the submit (`validate_nexus_password_rules`
  and `static/js/nexus-password.js` share one definition of the rules).
- The confirmation field is compared as it is typed, so a typo is caught before
  the form is sent.
- Destructive actions ask first (above).
- Destructive actions name the object: "Delete college Candon?" rather than
  "Are you sure?".
- `autocomplete`, `autocapitalize="none"` and `spellcheck="false"` are set on
  the fields where a phone keyboard would otherwise capitalise a username or a
  password.
- The sign-in form keeps the identifier after a failure and empties only the
  password, so a single-character typo does not mean retyping both.
- **The development sign-in page is now 404 when `DEBUG` is off.** It printed
  CSRF diagnostics, and it was reachable on the public site.

## 6. Recognition rather than recall

*Minimise memory load.*

- The password rules are visible *before* submission, not a message after
  failure; the met/unmet state is carried by text, not colour alone.
- The proposal wizard keeps the step list visible, marks the current step, and
  shows what is finished, so the user does not have to remember where they were.
- Confirmation messages name the thing that was saved or deleted
  (`"<title>" deleted successfully!`), so a refresh does not need to be
  reconstructed from memory.
- The Programs and Gallery pages say where their content comes from, so a
  visitor does not have to guess why a record is or is not listed.

## 7. Flexibility and efficiency of use

*Accelerators, invisible to the novice, speeding up the expert.*

- `autofocus` on the first field of the sign-in, registration and reset forms;
  Tab order follows the visual order.
- Skip-to-content link on every page, so a keyboard user does not walk the whole
  navigation to reach the form.
- Session-wide shortcuts that already existed (dashboard quick actions, bulk
  actions on list screens, filters kept in the query string) were left in place.
- Empty search/filter results keep the filter controls populated, so refining a
  search is one edit rather than starting over.

Not done: no keyboard shortcuts, no saved views.

## 8. Aesthetic and minimalist design

*A screen should not contain information that is irrelevant or rarely needed.*

- The sign-in card repeated "Sign in to continue" in the side panel, the page
  title, the card header and the button; the card now says "Welcome back" once
  and stops.
- The registration card repeated its own heading in the subtitle; the subtitle
  now says something the heading does not.
- The password rules block that used to be duplicated inside `register.html`
  (its own `<ul id="password-rules">` and its own inline script) is gone;
  there is one rules list, rendered by the shared script, and a `<noscript>`
  line states the rules when JavaScript is off.

## 9. Help users recognise, diagnose and recover from errors

*Plain-language errors that say what went wrong and how to fix it.*

- A failed submit renders a summary at the top of the form with one linked entry
  per field error, and the summary **takes focus on load**, so a screen-reader
  or keyboard user is told what happened instead of being left at the button.
  The summary is `role="alert"` and each entry links to `#<field id>`.
- Field-level errors stay next to the field as well; the summary is a route into
  them, not a replacement.
- Errors keep the user's input. Nothing is cleared to "help".
- Messages are written as instructions: "Enter a password with at least 8
  characters, one number, and one uppercase letter", not "Invalid input".
- Failure to send a reset email says so on the page and suggests trying again,
  rather than failing silently.
- Sign-in failures never disclose whether an address exists — "Invalid
  username/email or password" is deliberate.

## 10. Help and documentation

*Even though it is better if the system needs no documentation, it may be necessary to provide help.*

- Guidance is embedded directly where questions arise rather than behind separate
  `/about/` or `/help/` pages: Services outlines the extension workflow phases
  and wizard steps, registration and password forms display inline rule
  checklists, and Site Configuration controls published contact details without
  inventing addresses when none are set.
- Every wizard step and form field carries concise contextual help text right
  beside the input it governs.

## Verification

Held down by tests rather than by this document:

- `accounts/tests/test_ux_heuristics.py` — the reveal toggle is loaded on every
  page, password widgets carry the rules/match attributes, no template keeps its
  own rules list, failed sign-in and registration render a focusable summary
  with linked entries, forms declare their busy state, this audit documents all
  ten heuristics, the skip link and brand label work, and the debug sign-in page
  is 404.
- `tests/nexus-password.test.cjs` (9 tests) — the toggle, the rules checklist,
  the match hint and Caps Lock behaviour.
- `tests/nexus-forms.test.cjs` (15 tests) — error-summary focus, busy buttons,
  and the confirmation rules: asks before submitting, cancellation leaves the
  button untouched, links and outside buttons ask too, an empty message still
  asks, and a second `enhance()` does not double-ask.
- `accounts/tests/test_deletion_undo.py` (20 tests) — GET is refused on the three
  converted deletes, a restored row keeps its primary key, cascade and ordering,
  created/updated timestamps are put back, the bar names what was deleted,
  dismissing keeps it deleted, a token is scoped to its own session, expiry and
  the five-entry cap hold, and an oversized cascade is deleted without pretending
  it can be undone.
- `tests/nexus-undo.test.cjs` (8 tests) — the countdown, self-removal at zero,
  Escape, and a missing deadline being left alone.
- This document is itself checked: the test fails if any of the ten sections
  disappears.

## Known remaining gaps

1. The delete-draft dialog does not move focus into itself or trap it; Escape
   closes it, and the buttons are reachable, but focus order is the page's.
2. Long wizard steps show only the save button, not a step-level progress state.
3. Undo does not survive signing out, and it is not a retention policy: the
   snapshot lives in the session for fifteen minutes and then goes. A record
   deleted and left alone is gone — this is a safety net for a mis-click, not a
   recycle bin (that trade-off is written up in `accounts/deletion.py`).
4. Template files are not restored by undo (the object-storage file is not
   snapshotted), which is why those deletes still ask first.
5. The dashboard's dense tables were not re-cut for the ten heuristics in this
   round — only their confirmations and empty states were touched.
