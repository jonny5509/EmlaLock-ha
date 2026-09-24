# EmlaLock for Home Assistant

A Home Assistant custom integration for EmlaLock, including a bundled Lovelace card for displaying the current EmlaLock session and available actions.

## Features

- HACS-compatible Home Assistant custom integration
- EmlaLock session status and timing information
- Automatic discovery of EmlaLock entities
- Bundled **EmlaLock Card** (`custom:emlalock-card`)
- Session active/inactive status
- Start and end dates
- Elapsed and remaining time
- Minimum and maximum duration
- Requirement links
- Add/subtract duration controls
- Automatic detection of available holder-key actions
- Automatic card registration after installation

## Requirements

- Home Assistant with support for custom integrations
- A configured EmlaLock account/API connection
- HACS for the recommended installation method

## Installation

### HACS

1. Open **HACS → Integrations**.
2. Search for **EmlaLock**.
3. Install the integration.
4. Restart Home Assistant.
5. Go to **Settings → Devices & services → Add Integration**.
6. Search for **EmlaLock** and complete the configuration.

If EmlaLock is not listed in HACS yet, add this repository as a custom repository under **HACS → Integrations**:

`https://github.com/jonny5509/EmlaLock-ha`

### Manual installation

1. Download or clone this repository.
2. Copy the `custom_components/emlalock` directory into your Home Assistant `config/custom_components/` directory.
3. Restart Home Assistant.
4. Add **EmlaLock** from **Settings → Devices & services**.

## EmlaLock Card

The repository includes a bundled Lovelace card available as:

`custom:emlalock-card`

The card is packaged under `dist/emlalock-card.js` and is included with the integration so the integration and card can be installed together.

The card displays:

- Current EmlaLock session information
- Active/inactive status
- Start and end dates
- Elapsed and remaining time
- Minimum and maximum duration
- Requirement links
- Duration controls
- Holder-key action availability

The card automatically discovers the EmlaLock entities created by the integration, so entity IDs do not need to be entered manually.

## Dashboard setup

The card is automatically installed, loaded, and registered with Home Assistant. No manual JavaScript resource or YAML resource entry is required.

After installation and restart, add the card to a dashboard through the Home Assistant dashboard UI:

1. Open the dashboard you want to edit.
2. Select **Edit dashboard**.
3. Choose **Add card**.
4. Search for **EmlaLock Card** or select it from the available custom cards.
5. Save the dashboard.

You do not need to add entries to `configuration.yaml`, manually register a Lovelace resource, or provide EmlaLock entity IDs.

### Important Home Assistant limitation

A custom integration cannot silently modify an existing user's dashboard and insert a card into it. EmlaLock can automatically install, load, and register the card, but adding the card to an existing dashboard remains a dashboard UI action.

## Updates

After a HACS update:

1. Restart Home Assistant so the updated integration and bundled card are loaded.
2. Reload the dashboard if the updated card is not immediately visible.

## Troubleshooting

### EmlaLock is not available

Check that:

- The integration is installed under `custom_components/emlalock/`.
- Home Assistant has been restarted after installation.
- Your EmlaLock account/API configuration is valid.
- Home Assistant logs do not report an integration setup error.

### The card is not available

Check that:

- The integration has been installed successfully.
- Home Assistant has been restarted after installation or update.
- The bundled card file is present in the installed integration package.
- The browser has refreshed the dashboard after the update.

### The card cannot find entities

The card discovers entities created by the EmlaLock integration automatically. Confirm that the integration is loaded and that the expected EmlaLock entities are available in **Settings → Devices & services**.

## Development

The integration source is under `custom_components/emlalock/`.

The bundled card source/build files are maintained in the repository alongside the integration. When developing changes, verify both the Home Assistant integration and the Lovelace card after installation.

## Repository

Source code and issue tracking are hosted on GitHub:

`https://github.com/jonny5509/EmlaLock-ha`

## License

See the repository for the current project license.