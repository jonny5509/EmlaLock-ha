# User-specific calendar visibility and notifications

## What Home Assistant supports

This integration creates calendar and session entities at the Home Assistant instance level. It cannot determine which Home Assistant user is currently viewing an entity, and an integration option that lists users would not, by itself, secure the entity data from other users.

## Hide calendar cards from selected users

To show the integration's calendar only to selected household members:

1. Create a dashboard intended for the selected users.
2. Add the integration's calendar card to that dashboard.
3. In Home Assistant dashboard settings, configure who can access that dashboard, where supported by your Home Assistant version and dashboard type.
4. Do not add the calendar card to dashboards shared with other users.

This controls normal dashboard visibility; it is not entity-level access control. Users who can otherwise access the underlying entity may still be able to retrieve its data.

## Send notifications to selected users

Use a notification service that targets the intended user's device (for example, that user's mobile-app notify service) in the integration's **Phone to notify** setting. Avoid a broadcast service such as `notify.notify` if notifications must go to only one person's device. Configure each integration's notification toggles separately.

## Security note

Dashboard hiding is not a security boundary. Do not rely on it to protect sensitive session data from users who have broader Home Assistant access. Strong isolation requires Home Assistant access controls or separate instances that prevent those users from accessing the entity data.
