# EmlaLock for Home Assistant

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](https://github.com/jonny5509/EmlaLock-ha)
[![HACS](https://img.shields.io/badge/HACS-Custom%20Integration-41BDF5.svg)](https://hacs.xyz/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A Home Assistant custom integration for **EmlaLock**, including a bundled Lovelace card for displaying the current session and available actions.

## ✨ Features

- 🧩 HACS-compatible Home Assistant custom integration
- 🔄 Automatic discovery of EmlaLock entities
- 📊 Session status and timing information
- 🟢 Active/inactive session state
- 📅 Start and end dates
- ⏱️ Elapsed and remaining time
- ⏳ Minimum and maximum duration
- 🔗 Requirement links
- ➕➖ Add/subtract duration controls
- 🔑 Automatic detection of available holder-key actions
- 🖥️ Bundled **EmlaLock Card** (`custom:emlalock-card`)
- 📦 Integration and card distributed together

## 📋 Requirements

- Home Assistant with support for custom integrations
- A configured EmlaLock account/API connection
- [HACS](https://hacs.xyz/) for the recommended installation method

## 🚀 Installation

### HACS

1. Open **HACS → Integrations**.
2. Search for **EmlaLock** and select **Download**.
3. Restart Home Assistant.
4. Open **Settings → Devices & services**.
5. Select **Add Integration**.
6. Search for **EmlaLock** and complete the configuration.

If EmlaLock is not yet listed in HACS, add this repository as a custom repository:

`https://github.com/jonny5509/EmlaLock-ha`

### Manual installation

1. Download or clone this repository.
2. Copy `custom_components/emlalock` into your Home Assistant `config/custom_components/` directory.
3. Restart Home Assistant.
4. Open **Settings → Devices & services → Add Integration**.
5. Search for **EmlaLock** and complete setup.

## 🖥️ EmlaLock Card

The repository includes a bundled Lovelace card:

`custom:emlalock-card`

The card is packaged with the integration so both components can be installed together.

It displays:

- Current session information
- Active/inactive status
- Start and end dates
- Elapsed and remaining time
- Minimum and maximum duration
- Requirement links
- Duration controls
- Available holder-key actions

The card automatically discovers EmlaLock entities created by the integration, so entity IDs do not need to be entered manually.

## 📐 Dashboard setup

The card is automatically installed, loaded, and registered with Home Assistant. No manual JavaScript resource or YAML resource entry is required.

After installation and restart:

1. Open the dashboard you want to edit.
2. Select **Edit dashboard**.
3. Choose **Add card**.
4. Search for **EmlaLock Card** or select it from the available custom cards.
5. Save the dashboard.

### Important Home Assistant limitation

A custom integration cannot silently modify an existing user's dashboard. EmlaLock can install, load, and register the card automatically, but adding the card to an existing dashboard remains a dashboard UI action.

## 🔄 Updates

After a HACS update:

1. Restart Home Assistant so the updated integration and bundled card are loaded.
2. Reload the dashboard if the updated card is not immediately visible.

## 🧰 Troubleshooting

### EmlaLock is not available

Check that:

- `custom_components/emlalock/` is installed correctly.
- Home Assistant has been restarted after installation.
- Your EmlaLock account/API configuration is valid.
- Home Assistant logs do not report an integration setup error.

### The card is not available

Check that:

- The integration has been installed successfully.
- Home Assistant has been restarted after installation or update.
- The bundled card file is present in the installed integration package.
- Your browser/dashboard has been refreshed.

### The card cannot find entities

The card discovers entities created by the EmlaLock integration automatically. Confirm that the integration is loaded and the expected EmlaLock entities are available under **Settings → Devices & services**.

## 👩‍💻 Development

Integration source code is under:

`custom_components/emlalock/`

The bundled card source/build files are maintained alongside the integration. When making changes, verify both the Home Assistant integration and the Lovelace card after installation.

## 🔗 Links

- [Repository](https://github.com/jonny5509/EmlaLock-ha)
- [Issues](https://github.com/jonny5509/EmlaLock-ha/issues)

## 📄 License

See [LICENSE](LICENSE) for the current project license.
