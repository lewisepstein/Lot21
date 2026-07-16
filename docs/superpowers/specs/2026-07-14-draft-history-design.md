# Draft History — Never Lose a Previous Version (Feature B)

## Goal
Every version of a piece of content is saved automatically, listed with timestamps,
restorable in one click, and comparable side by side. No content is ever lost.

## Key insight: the data already exists
`prompt_history` already stores every generated/edited draft as its own row
(`id`, `content_id`, `prompt_session_id`, `user_prompt`, `ai_response` JSON,
`prompt_action`, `created_on`). Drafts, approvals, and rejections only ever ADD
rows — nothing is overwritten. So "versions" = prompt_history rows for a
content_id, and this feature is mostly exposing that data plus a restore action.
No schema change.

The content page's shown content comes from `content.generated_content` (set at
create time); the AI-panel thread comes from `prompt_history`. Restore therefore
operates on the prompt_history thread (the versions the user actually iterates on),
matching how draft/approve already behave.

## Restore semantics: non-destructive (append)
Restoring an old version creates a NEW `prompt_history` row that copies the chosen
version's `ai_response`, marked `prompt_action = RESTORE`, in the content's current
session, so it becomes the latest version. The old rows are untouched. This
guarantees "nothing is ever lost" and avoids any flag/schema change that could
ripple into existing latest-draft logic.

## Backend
- `get_content_version_history(content_id)` in `prompt_history_utils.py`
  - All non-deleted prompt_history rows for the content, newest first.
  - Each: `{id, created_on, user_prompt, prompt_action, text, preview}` where
    `text` is the extracted response text (via existing `_extract_response_text`)
    and `preview` is the first ~120 chars. Rows with no response text are skipped.
- `restore_content_version(content_id, version_id, user_id)` in
  `prompt_history_utils.py`
  - Reads the chosen row (must belong to content_id); copies its `ai_response`
    into a new row: `prompt_action=RESTORE`, `prompt_type=TEXT`, session = the
    content's most recent session, `user_prompt` = `"Restored version from <ts>"`.
  - Returns the new row dict.
- Endpoints (in `content_module/prompt_history.py`, `tags=["user"]`, bearer auth
  like the others):
  - `GET  /user/content/{content_id}/history` → `{versions: [...]}`
  - `POST /user/content/{content_id}/restore/{version_id}` → new version row
- Response models added to `content_responses.py` as needed.

## Frontend (`content.htm`)
- A "History" button (clock icon, `bi-clock-history`) in the AI panel header.
- Clicking opens a Bootstrap offcanvas/modal listing versions:
  - Row = timestamp (localized) + the prompt that produced it + an action badge
    (Draft / Approved / Rejected / Restored).
  - Each row: a **Restore** button and a **compare** checkbox (max 2 selected).
- **Restore**: POST restore endpoint → on success, close panel, `loadPromptHistory()`
  to re-render the thread (the restored version is now latest), toast
  "Version restored".
- **Compare** (2 selected): open a modal with two columns (older left, newer
  right) and word-level change highlighting computed client-side (simple LCS
  word diff, no external library — CSP/self-contained safe). Added words
  highlighted on the right, removed words on the left.

## Non-goals / YAGNI
- No editing of historical versions in place.
- No cross-content history; scoped to one content_id.
- Restore does not modify `content.generated_content` (consistent with existing
  draft/approve behavior).

## Testing
- History lists every prompt_history version for a content, newest first,
  skipping empty/error responses.
- Restore adds exactly one new RESTORE row copying the chosen version's text; old
  rows unchanged; new row is latest.
- Word-diff highlights only changed tokens between two versions.
- Regression: existing generate / save-as-draft / approve / reject flows and the
  session thread render unchanged.
