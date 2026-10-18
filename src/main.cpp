#include <M5Unified.h>

#include "ble_transport.h"
#include "display_ui.h"
#include "image_receiver.h"

namespace
{
bool gConnected = false;

void handleCompleted()
{
    const uint8_t *data;
    size_t length;
    bool crcOk;
    if (!image_receiver::takeCompleted(&data, &length, &crcOk))
    {
        return;
    }
    display_ui::hideProgress();
    if (!crcOk)
    {
        image_receiver::finish("crc");
    }
    else if (!display_ui::showImage(data, length))
    {
        image_receiver::finish("decode");
    }
    else
    {
        image_receiver::finish(nullptr);
    }
}
} // namespace

void setup()
{
    auto config = M5.config();
    M5.begin(config);
    Serial.begin(115200);

    if (!display_ui::begin())
    {
        Serial.println("failed to allocate canvas");
    }

    char info[64];
    snprintf(info, sizeof(info), "width=%d height=%d max_length=%lu", display_ui::width(), display_ui::height(),
             static_cast<unsigned long>(image_receiver::kMaxLength));
    image_receiver::begin(ble_transport::notify);
    ble_transport::begin(image_receiver::onReceive, image_receiver::onDisconnect, info);
    display_ui::setDeviceName(ble_transport::deviceName());
    Serial.printf("advertising as %s (%s)\n", ble_transport::deviceName(), info);
}

void loop()
{
    M5.update();
    uint32_t now = millis();

    bool connected = ble_transport::isConnected();
    if (connected != gConnected)
    {
        gConnected = connected;
        display_ui::setConnected(connected);
    }

    image_receiver::poll(now);

    image_receiver::Progress progress = image_receiver::progress();
    if (progress.state == image_receiver::State::Receiving)
    {
        display_ui::showProgress(progress.received, progress.length);
    }
    else if (progress.state == image_receiver::State::Idle)
    {
        display_ui::hideProgress();
    }

    handleCompleted();

    if (const char *error = image_receiver::takeError())
    {
        Serial.printf("error: %s\n", error);
        char message[48];
        snprintf(message, sizeof(message), "Error: %s", error);
        display_ui::showToast(message);
    }

    display_ui::update(now);
    delay(5);
}
