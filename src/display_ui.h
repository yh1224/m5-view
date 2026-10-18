#pragma once

#include <cstddef>
#include <cstdint>

// Screen output (idle screen, image, progress bar, toast).
// Call from loop().
namespace display_ui
{
// Set the screen to landscape. Returns false if the canvases cannot be
// allocated
bool begin();

// Screen size in landscape
int width();
int height();

// Show the idle screen with the device name
void setDeviceName(const char *deviceName);

// Update the connection status on the idle screen
void setConnected(bool connected);

// Decode and show a PNG, scaled to fit the screen if its size differs. On
// decode failure, keep the previous image and return false
bool showImage(const uint8_t *png, size_t length);

void showProgress(uint32_t received, uint32_t total);
void hideProgress();

void showToast(const char *message);

// Hide the toast once it expires
void update(uint32_t nowMs);
} // namespace display_ui
