# Per-user calendar and notification visibility: implementation requirements

This draft tracks the implementation work for per-user visibility and notification routing.

## Required behavior

- Let an administrator select Home Assistant users for integration notifications.
- Send notifications only to explicitly configured recipient targets; never silently fall back to the broadcast `notify.notify` target for this feature.
- If no recipients are selected, send no notifications.
- Support per-user calendar presentation using Home Assistant's dashboard/view/card visibility conditions.
- If no users are selected for calendar presentation, omit the calendar from the integration's generated or documented user-facing dashboard configuration.
- Preserve existing behavior for installations that have not enabled the new options, unless a release explicitly documents a migration.
- Include translations, config/options flow validation, tests for empty selections and recipient routing, and migration handling for existing config entries.

## Home Assistant limitation

Dashboard visibility is a presentation control, not a security boundary: a hidden view's URL may still be accessible. Where entity-level privacy is required, use Home Assistant's supported entity permissions. A dashboard selector alone must not be described as preventing entity access.

## Acceptance criteria

- [ ] Options flow exposes clear user selection for notifications and calendar presentation.
- [ ] Empty selections hide/disable the corresponding feature and never silently fall back to broadcasting.
- [ ] Selected users receive notifications only through explicitly configured per-user notify targets.
- [ ] Calendar visibility instructions/configuration are tied to selected Home Assistant user IDs.
- [ ] Existing installations migrate safely and retain unrelated settings.
- [ ] Automated tests cover selected users, empty selections, and backward compatibility.
- [ ] Documentation and translations are updated.

**Scope note:** This document records requirements only. Runtime behavior is not changed by this draft PR; implementation and tests remain required before merge.
