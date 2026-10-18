#include "ble_transport.h"

#include <sdkconfig.h>

#if !defined(CONFIG_IDF_TARGET_ESP32P4)

#include <atomic>
#include <cstdio>
#include <cstring>

#include <NimBLEDevice.h>
#include <esp_mac.h>

namespace ble_transport
{
namespace
{
constexpr const char *kServiceUuid = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E";
constexpr const char *kRxUuid = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E";
constexpr const char *kTxUuid = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E";
constexpr const char *kInfoUuid = "6E400004-B5A3-F393-E0A9-E50E24DCCA9E";
constexpr uint16_t kPreferredMtu = 517;

char gDeviceName[32];
NimBLECharacteristic *gTx = nullptr;
std::atomic<bool> gConnected{false};
ReceiveCallback gOnReceive = nullptr;
DisconnectCallback gOnDisconnect = nullptr;

class ServerCallbacks : public NimBLEServerCallbacks
{
    void onConnect(NimBLEServer *server, NimBLEConnInfo &connInfo) override
    {
        gConnected = true;
    }

    void onDisconnect(NimBLEServer *server, NimBLEConnInfo &connInfo, int reason) override
    {
        gConnected = false;
        if (gOnDisconnect)
        {
            gOnDisconnect();
        }
    }
};

class RxCallbacks : public NimBLECharacteristicCallbacks
{
    void onWrite(NimBLECharacteristic *characteristic, NimBLEConnInfo &connInfo) override
    {
        NimBLEAttValue value = characteristic->getValue();
        if (gOnReceive)
        {
            gOnReceive(value.data(), value.size());
        }
    }
};

ServerCallbacks gServerCallbacks;
RxCallbacks gRxCallbacks;
} // namespace

void begin(ReceiveCallback onReceive, DisconnectCallback onDisconnect, const char *info)
{
    gOnReceive = onReceive;
    gOnDisconnect = onDisconnect;

    uint8_t mac[6];
    esp_read_mac(mac, ESP_MAC_BT);
    snprintf(gDeviceName, sizeof(gDeviceName), "M5-View-%02X%02X", mac[4], mac[5]);

    NimBLEDevice::init(gDeviceName);
    NimBLEDevice::setMTU(kPreferredMtu);

    NimBLEServer *server = NimBLEDevice::createServer();
    server->setCallbacks(&gServerCallbacks, false);
    server->advertiseOnDisconnect(true);

    NimBLEService *service = server->createService(kServiceUuid);
    NimBLECharacteristic *rx =
        service->createCharacteristic(kRxUuid, NIMBLE_PROPERTY::WRITE | NIMBLE_PROPERTY::WRITE_NR);
    rx->setCallbacks(&gRxCallbacks);
    gTx = service->createCharacteristic(kTxUuid, NIMBLE_PROPERTY::NOTIFY);
    service->createCharacteristic(kInfoUuid, NIMBLE_PROPERTY::READ)->setValue(info);
    server->start();

    // A 128-bit UUID and the name do not fit in 31 bytes, so the name goes in
    // the scan response
    NimBLEAdvertisementData advertisementData;
    advertisementData.setFlags(BLE_HS_ADV_F_DISC_GEN | BLE_HS_ADV_F_BREDR_UNSUP);
    advertisementData.addServiceUUID(NimBLEUUID(kServiceUuid));
    NimBLEAdvertisementData scanResponseData;
    scanResponseData.setName(gDeviceName);

    NimBLEAdvertising *advertising = NimBLEDevice::getAdvertising();
    advertising->setAdvertisementData(advertisementData);
    advertising->setScanResponseData(scanResponseData);
    advertising->enableScanResponse(true);
    advertising->start();
}

const char *deviceName()
{
    return gDeviceName;
}

bool isConnected()
{
    return gConnected;
}

void notify(const char *message)
{
    if (!gTx || !gConnected)
    {
        return;
    }
    char line[64];
    int length = snprintf(line, sizeof(line), "%s\n", message);
    if (length <= 0)
    {
        return;
    }
    gTx->notify(reinterpret_cast<const uint8_t *>(line), static_cast<size_t>(length));
}
} // namespace ble_transport

#endif // !CONFIG_IDF_TARGET_ESP32P4
