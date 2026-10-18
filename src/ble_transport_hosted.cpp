#include "ble_transport.h"

#include <sdkconfig.h>

#if defined(CONFIG_IDF_TARGET_ESP32P4)

#include <atomic>
#include <cstdio>

#include <BLEDevice.h>
#include <BLEServer.h>
#include <host/ble_hs.h>
#include <services/gap/ble_svc_gap.h>

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
BLECharacteristic *gTx = nullptr;
std::atomic<bool> gConnected{false};
ReceiveCallback gOnReceive = nullptr;
DisconnectCallback gOnDisconnect = nullptr;

class ServerCallbacks : public BLEServerCallbacks
{
    void onConnect(BLEServer *server) override
    {
        gConnected = true;
    }

    void onDisconnect(BLEServer *server) override
    {
        gConnected = false;
        if (gOnDisconnect)
        {
            gOnDisconnect();
        }
    }
};

class RxCallbacks : public BLECharacteristicCallbacks
{
    void onWrite(BLECharacteristic *characteristic) override
    {
        if (gOnReceive)
        {
            gOnReceive(characteristic->getData(), characteristic->getLength());
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

    // The BLE address belongs to the ESP32-C6 and is known only after init, so
    // set the final name afterwards
    BLEDevice::init("M5-View");
    uint8_t mac[6] = {};
    if (ble_hs_id_copy_addr(BLE_ADDR_PUBLIC, mac, nullptr) != 0)
    {
        ble_hs_id_copy_addr(BLE_ADDR_RANDOM, mac, nullptr);
    }
    // NimBLE stores the address little-endian
    snprintf(gDeviceName, sizeof(gDeviceName), "M5-View-%02X%02X", mac[1], mac[0]);
    ble_svc_gap_device_name_set(gDeviceName);
    BLEDevice::setMTU(kPreferredMtu);

    BLEServer *server = BLEDevice::createServer();
    server->setCallbacks(&gServerCallbacks);
    server->advertiseOnDisconnect(true);

    BLEService *service = server->createService(kServiceUuid);
    BLECharacteristic *rx = service->createCharacteristic(
        kRxUuid, BLECharacteristic::PROPERTY_WRITE | BLECharacteristic::PROPERTY_WRITE_NR);
    rx->setCallbacks(&gRxCallbacks);
    gTx = service->createCharacteristic(kTxUuid, BLECharacteristic::PROPERTY_NOTIFY);
    service->createCharacteristic(kInfoUuid, BLECharacteristic::PROPERTY_READ)->setValue(String(info));
    service->start();

    // A 128-bit UUID and the name do not fit in 31 bytes, so the name goes in
    // the scan response
    BLEAdvertisementData advertisementData;
    advertisementData.setFlags(BLE_HS_ADV_F_DISC_GEN | BLE_HS_ADV_F_BREDR_UNSUP);
    advertisementData.setCompleteServices(BLEUUID(kServiceUuid));
    BLEAdvertisementData scanResponseData;
    scanResponseData.setName(gDeviceName);

    BLEAdvertising *advertising = BLEDevice::getAdvertising();
    advertising->setAdvertisementData(advertisementData);
    advertising->setScanResponseData(scanResponseData);
    advertising->setScanResponse(true);
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
    gTx->setValue(reinterpret_cast<const uint8_t *>(line), static_cast<size_t>(length));
    gTx->notify();
}
} // namespace ble_transport

#endif // CONFIG_IDF_TARGET_ESP32P4
