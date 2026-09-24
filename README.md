# EmlaLock for Home Assistant

Home Assistant custom integration for EmlaLock.

## Installation via HACS

Install **EmlaLock** from HACS and configure the integration with your EmlaLock user/API details.

The repository also includes the **EmlaLock Card**, packaged like a HACS community card and bundled with the integration. The card is automatically served and registered by the integration after installation.

### No manual dashboard resource or YAML is required

After installing or updating EmlaLock and restarting Home Assistant:

- no `configuration.yaml` entry is required
- no manual Lovelace resource URL is required
- no JavaScript resource needs to be added manually
- no entity IDs need to be entered in the card
- no card YAML configuration is required
- the **EmlaLock Card** is registered with Home Assistant and appears in the dashboard card picker

The card automatically discovers the EmlaLock entities and action buttons created by the integration.

## Card

The bundled card is available as `custom:emlalock-card`. It is packaged in the repository under `dist/emlalock-card.js` and inside the installed integration package so HACS installation and automatic registration work together.

The card provides:

- EmlaLock session information
- session active/inactive status
- start and end dates
- elapsed and remaining time
- minimum and maximum duration
- requirement links
- add/subtract duration controls
- automatic detection of whether holder-key actions are available

You do not need to specify the EmlaLock entity IDs manually.

## Important Home Assistant limitation

Home Assistant does not provide a supported mechanism for a custom integration to silently modify an existing user's dashboard and insert a card into it. Therefore the card is automatically installed, loaded, registered, and available in the card picker, but adding it to an existing dashboard is still a dashboard UI action.

## Updates

After a HACS update, restart Home Assistant so the updated integration and bundled card are loaded.
