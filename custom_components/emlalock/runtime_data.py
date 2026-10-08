from __future__ import annotations

from dataclasses import dataclass

from .api import EmlaLockApi
from .coordinator import EmlaLockCoordinator
from homeassistant.config_entries import ConfigEntry


@dataclass(slots=True)
class EmlaLockRuntimeData:
    """Runtime data for an EmlaLock config entry."""

    api: EmlaLockApi
    coordinator: EmlaLockCoordinator


type EmlaLockConfigEntry = ConfigEntry[EmlaLockRuntimeData]
