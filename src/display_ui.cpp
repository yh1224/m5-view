#include "display_ui.h"

#include <utility>

#include <M5Unified.h>

namespace display_ui
{
namespace
{
constexpr int kWidth = 320;
constexpr int kHeight = 240;
constexpr uint8_t kBrightness = 128;
constexpr int kProgressHeight = 6;
constexpr int kToastHeight = 32;
constexpr uint32_t kToastDurationMs = 3000;

M5Canvas gCanvasA(&M5.Display);
M5Canvas gCanvasB(&M5.Display);
M5Canvas *gCurrent = &gCanvasA; // Shown image (idle screen until one arrives)
M5Canvas *gStaging = &gCanvasB; // Decode target

const char *gDeviceName = "";
bool gConnected = false;
bool gHasImage = false;
bool gProgressVisible = false;
int gProgressWidth = -1;
bool gToastVisible = false;
uint32_t gToastStartMs = 0;

bool createCanvas(M5Canvas &canvas)
{
    canvas.setColorDepth(16);
    canvas.setPsram(true);
    return canvas.createSprite(kWidth, kHeight) != nullptr;
}

void renderIdleScreen()
{
    gCurrent->fillScreen(TFT_BLACK);
    gCurrent->setTextDatum(middle_center);
    gCurrent->setFont(&fonts::FreeSansBold12pt7b);
    gCurrent->setTextColor(TFT_WHITE);
    gCurrent->drawString(gDeviceName, kWidth / 2, kHeight / 2 - 16);
    gCurrent->setFont(&fonts::FreeSans9pt7b);
    gCurrent->setTextColor(gConnected ? TFT_GREEN : TFT_DARKGREY);
    gCurrent->drawString(gConnected ? "Connected" : "Advertising", kWidth / 2, kHeight / 2 + 16);
}

void drawProgressBar()
{
    int y = kHeight - kProgressHeight;
    M5.Display.fillRect(0, y, kWidth, kProgressHeight, TFT_DARKGREY);
    M5.Display.fillRect(0, y, gProgressWidth, kProgressHeight, TFT_CYAN);
}

// Push the canvas to the screen and redraw the active overlays
void redraw()
{
    gCurrent->pushSprite(0, 0);
    if (gProgressVisible)
    {
        drawProgressBar();
    }
}
} // namespace

bool begin(const char *deviceName)
{
    gDeviceName = deviceName;
    if (M5.Display.width() < M5.Display.height())
    {
        M5.Display.setRotation(M5.Display.getRotation() ^ 1);
    }
    M5.Display.setBrightness(kBrightness);
    M5.Display.fillScreen(TFT_BLACK);

    if (!createCanvas(gCanvasA) || !createCanvas(gCanvasB))
    {
        return false;
    }
    renderIdleScreen();
    redraw();
    return true;
}

void setConnected(bool connected)
{
    gConnected = connected;
    if (!gHasImage)
    {
        renderIdleScreen();
        redraw();
    }
}

bool showImage(const uint8_t *png, size_t length)
{
    gStaging->fillScreen(TFT_BLACK);
    if (!gStaging->drawPng(png, length, 0, 0))
    {
        return false;
    }
    std::swap(gCurrent, gStaging);
    gHasImage = true;
    gToastVisible = false;
    redraw();
    return true;
}

void showProgress(uint32_t received, uint32_t total)
{
    int width = total > 0 ? static_cast<int>(static_cast<uint64_t>(received) * kWidth / total) : 0;
    if (gProgressVisible && width == gProgressWidth)
    {
        return;
    }
    gProgressVisible = true;
    gProgressWidth = width;
    drawProgressBar();
}

void hideProgress()
{
    if (!gProgressVisible)
    {
        return;
    }
    gProgressVisible = false;
    gProgressWidth = -1;
    redraw();
}

void showToast(const char *message)
{
    int y = kHeight - kToastHeight;
    M5.Display.fillRect(0, y, kWidth, kToastHeight, TFT_RED);
    M5.Display.setTextDatum(middle_center);
    M5.Display.setFont(&fonts::FreeSans9pt7b);
    M5.Display.setTextColor(TFT_WHITE);
    M5.Display.drawString(message, kWidth / 2, y + kToastHeight / 2);
    gToastVisible = true;
    gToastStartMs = millis();
}

void update(uint32_t nowMs)
{
    if (gToastVisible && nowMs - gToastStartMs >= kToastDurationMs)
    {
        gToastVisible = false;
        redraw();
    }
}
} // namespace display_ui
