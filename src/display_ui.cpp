#include "display_ui.h"

#include <algorithm>
#include <utility>

#include <M5Unified.h>

namespace display_ui
{
namespace
{
// UI sizes below are for 320 px wide and scaled by gScale
constexpr int kBaseWidth = 320;
constexpr uint8_t kBrightness = 128;
constexpr int kProgressHeight = 6;
constexpr int kToastHeight = 32;
constexpr uint32_t kToastDurationMs = 3000;

M5Canvas gCanvasA(&M5.Display);
M5Canvas gCanvasB(&M5.Display);
M5Canvas *gCurrent = &gCanvasA; // Shown image (idle screen until one arrives)
M5Canvas *gStaging = &gCanvasB; // Decode target

int gWidth = 0;
int gHeight = 0;
int gScale = 1;
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
    return canvas.createSprite(gWidth, gHeight) != nullptr;
}

// Use the larger fonts on large screens so scaled text stays smooth
void setTitleFont(lgfx::LovyanGFX &gfx)
{
    gfx.setFont(gScale >= 2 ? &fonts::FreeSansBold24pt7b : &fonts::FreeSansBold12pt7b);
    gfx.setTextSize(std::max(1, gScale / 2));
}

void setBodyFont(lgfx::LovyanGFX &gfx)
{
    gfx.setFont(gScale >= 2 ? &fonts::FreeSans18pt7b : &fonts::FreeSans9pt7b);
    gfx.setTextSize(std::max(1, gScale / 2));
}

void renderIdleScreen()
{
    gCurrent->fillScreen(TFT_BLACK);
    gCurrent->setTextDatum(middle_center);
    setTitleFont(*gCurrent);
    gCurrent->setTextColor(TFT_WHITE);
    gCurrent->drawString(gDeviceName, gWidth / 2, gHeight / 2 - 16 * gScale);
    setBodyFont(*gCurrent);
    gCurrent->setTextColor(gConnected ? TFT_GREEN : TFT_DARKGREY);
    gCurrent->drawString(gConnected ? "Connected" : "Advertising", gWidth / 2, gHeight / 2 + 16 * gScale);
}

void drawProgressBar()
{
    int height = kProgressHeight * gScale;
    int y = gHeight - height;
    M5.Display.fillRect(0, y, gWidth, height, TFT_DARKGREY);
    M5.Display.fillRect(0, y, gProgressWidth, height, TFT_CYAN);
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

bool begin()
{
    if (M5.Display.width() < M5.Display.height())
    {
        M5.Display.setRotation(M5.Display.getRotation() ^ 1);
    }
    gWidth = M5.Display.width();
    gHeight = M5.Display.height();
    gScale = std::max(1, gWidth / kBaseWidth);
    M5.Display.setBrightness(kBrightness);
    M5.Display.fillScreen(TFT_BLACK);

    return createCanvas(gCanvasA) && createCanvas(gCanvasB);
}

int width()
{
    return gWidth;
}

int height()
{
    return gHeight;
}

void setDeviceName(const char *deviceName)
{
    gDeviceName = deviceName;
    if (!gHasImage)
    {
        renderIdleScreen();
        redraw();
    }
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
    // Zoom 0 fits the image to the canvas keeping the aspect ratio. An image
    // of the screen size is drawn at 1:1
    if (!gStaging->drawPng(png, length, 0, 0, 0, 0, 0, 0, 0.0f, 0.0f, middle_center))
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
    int width = total > 0 ? static_cast<int>(static_cast<uint64_t>(received) * gWidth / total) : 0;
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
    int height = kToastHeight * gScale;
    int y = gHeight - height;
    M5.Display.fillRect(0, y, gWidth, height, TFT_RED);
    M5.Display.setTextDatum(middle_center);
    setBodyFont(M5.Display);
    M5.Display.setTextColor(TFT_WHITE);
    M5.Display.drawString(message, gWidth / 2, y + height / 2);
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
