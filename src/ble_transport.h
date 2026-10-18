#pragma once

#include <cstddef>
#include <cstdint>

// BLE peripheral providing the Nordic UART Service (NUS) and the Info
// characteristic. Callbacks run on the NimBLE host task.
// ble_transport_nimble.cpp (NimBLE-Arduino) and ble_transport_hosted.cpp
// (Arduino core BLE over ESP-Hosted) implement it for each board.
namespace ble_transport
{
using ReceiveCallback = void (*)(const uint8_t *data, size_t length);
using DisconnectCallback = void (*)();

// Initialize BLE and start advertising. info is the value of the Info
// characteristic (docs/protocol.md §1.4)
void begin(ReceiveCallback onReceive, DisconnectCallback onDisconnect, const char *info);

// Advertised device name (M5-View-XXXX)
const char *deviceName();

bool isConnected();

// Send a TX notification to the connected central
void notify(const char *message);
} // namespace ble_transport
