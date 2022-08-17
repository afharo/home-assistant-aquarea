"""The Aquarea Smart Cloud integration."""
from __future__ import annotations
from typing import Any


from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession

import aioaquarea
from homeassistant.helpers.entity import DeviceInfo

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DEVICES, DOMAIN, CLIENT
from .coordinator import AquareaDataUpdateCoordinator

# TODO List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
PLATFORMS: list[Platform] = [Platform.SENSOR]


def initialize_data(hass: HomeAssistant, entry: ConfigEntry) -> None:
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    if entry.entry_id not in hass.data[DOMAIN]:
        hass.data[DOMAIN][entry.entry_id] = {
            CLIENT: None,
            DEVICES: dict[str, AquareaDataUpdateCoordinator](),
        }


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Aquarea Smart Cloud from a config entry."""

    initialize_data(hass, entry)

    client = hass.data[DOMAIN].get(entry.entry_id).get(CLIENT)
    if not client:
        username = entry.data.get(CONF_USERNAME)
        password = entry.data.get(CONF_PASSWORD)
        session = async_create_clientsession(hass)
        client = aioaquarea.Client(session, username, password)
        hass.data[DOMAIN][entry.entry_id][CLIENT] = client

    # Get all the devices, we will filter the disabled ones later
    devices = await client.get_devices(include_long_id=True)

    # We create a Cordinator per Device and store it in the hass.data[DOMAIN] dict to be able to access it from the platform
    for device in devices:
        coordinator = AquareaDataUpdateCoordinator(
            hass=hass, entry=entry, client=client, device_info=device
        )
        hass.data[DOMAIN][entry.entry_id][DEVICES][device.device_id] = coordinator
        await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class AquareaBaseEntity(CoordinatorEntity[AquareaDataUpdateCoordinator]):
    """Common base for Aquarea entities."""

    coordinator: AquareaDataUpdateCoordinator
    _attr_attribution = ATTRIBUTION

    def __init__(self, coordinator: AquareaDataUpdateCoordinator) -> None:
        """Initialize entity."""
        super().__init__(coordinator)

        self._attrs: dict[str, Any] = {
            "name": self.coordinator.device.name,
            "id": self.coordinator.device.device_id,
        }
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.device.device_id)},
            manufacturer=self.coordinator.device.manufacturer,
            model="",
            name=self.coordinator.device.name,
            sw_version=self.coordinator.device.version,
        )
        self._attr_unique_id = self.coordinator.device.device_id

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()
