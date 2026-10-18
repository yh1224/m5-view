#pragma once

#include <cstddef>
#include <cstdint>

// BLE peripheral providing the Nordic UART Service (NUS).
// Callbacks run on the NimBLE host task.
namespace ble_transport
{
using ReceiveCallback = void (*)(const uint8_t *data, size_t length);
using DisconnectCallback = void (*)();

// Initialize NimBLE and start advertising
void begin(ReceiveCallback onReceive, DisconnectCallback onDisconnect);

// Advertised device name (M5-View-XXXX)
const char *deviceName();

bool isConnected();

// Send a TX notification to the connected central
void notify(const char *message);
} // namespace ble_transport
