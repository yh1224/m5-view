#include "image_receiver.h"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <mutex>

#include <Arduino.h>

namespace image_receiver
{
namespace
{
constexpr uint8_t kMagic[4] = {'I', 'M', 'G', '0'};
constexpr size_t kHeaderSize = 12;
constexpr uint32_t kAckWindow = 4096;
constexpr uint32_t kTimeoutMs = 5000;

std::mutex gMutex;
NotifyFunction gNotify = nullptr;
State gState = State::Idle;
uint8_t *gBuffer = nullptr;
uint32_t gLength = 0;
uint32_t gExpectedCrc = 0;
uint32_t gReceived = 0;
uint32_t gLastReceiveMs = 0;
const char *gError = nullptr;

uint32_t readUint32Le(const uint8_t *p)
{
    return static_cast<uint32_t>(p[0]) | (static_cast<uint32_t>(p[1]) << 8) |
           (static_cast<uint32_t>(p[2]) << 16) | (static_cast<uint32_t>(p[3]) << 24);
}

// zlib-compatible CRC32 (polynomial 0xEDB88320)
uint32_t crc32(const uint8_t *data, size_t length)
{
    static uint32_t table[256];
    static bool initialized = false;
    if (!initialized)
    {
        for (uint32_t i = 0; i < 256; i++)
        {
            uint32_t c = i;
            for (int k = 0; k < 8; k++)
            {
                c = (c & 1) ? (0xEDB88320u ^ (c >> 1)) : (c >> 1);
            }
            table[i] = c;
        }
        initialized = true;
    }
    uint32_t crc = 0xFFFFFFFFu;
    for (size_t i = 0; i < length; i++)
    {
        crc = table[(crc ^ data[i]) & 0xFF] ^ (crc >> 8);
    }
    return crc ^ 0xFFFFFFFFu;
}

// Call with gMutex held
void resetLocked()
{
    free(gBuffer);
    gBuffer = nullptr;
    gLength = 0;
    gExpectedCrc = 0;
    gReceived = 0;
    gState = State::Idle;
}

// Call with gMutex held. Writes the message to notify into message
void failLocked(const char *reason, char *message, size_t messageSize)
{
    resetLocked();
    gError = reason;
    snprintf(message, messageSize, "ERR %s", reason);
}

void sendNotify(const char *message)
{
    if (gNotify && message[0] != '\0')
    {
        gNotify(message);
    }
}

// Call with gMutex held
void handleHeaderLocked(const uint8_t *data, size_t length, char *message, size_t messageSize)
{
    if (length != kHeaderSize || memcmp(data, kMagic, sizeof(kMagic)) != 0)
    {
        failLocked("bad_header", message, messageSize);
        return;
    }
    uint32_t bodyLength = readUint32Le(data + 4);
    if (bodyLength == 0)
    {
        failLocked("bad_header", message, messageSize);
        return;
    }
    if (bodyLength > kMaxLength)
    {
        failLocked("too_large", message, messageSize);
        return;
    }
    gBuffer = static_cast<uint8_t *>(ps_malloc(bodyLength));
    if (!gBuffer)
    {
        failLocked("no_memory", message, messageSize);
        return;
    }
    gLength = bodyLength;
    gExpectedCrc = readUint32Le(data + 8);
    gReceived = 0;
    gLastReceiveMs = millis();
    gState = State::Receiving;
}

// Call with gMutex held
void handleBodyLocked(const uint8_t *data, size_t length, char *message, size_t messageSize)
{
    if (length > gLength - gReceived)
    {
        failLocked("overflow", message, messageSize);
        return;
    }
    uint32_t before = gReceived;
    memcpy(gBuffer + gReceived, data, length);
    gReceived += length;
    gLastReceiveMs = millis();

    if (gReceived == gLength)
    {
        gState = State::Processing;
    }
    else if (gReceived / kAckWindow != before / kAckWindow)
    {
        snprintf(message, messageSize, "ACK %lu",
                 static_cast<unsigned long>(gReceived / kAckWindow * kAckWindow));
    }
}
} // namespace

void begin(NotifyFunction notify)
{
    gNotify = notify;
}

void onReceive(const uint8_t *data, size_t length)
{
    char message[32] = "";
    {
        std::lock_guard<std::mutex> lock(gMutex);
        switch (gState)
        {
        case State::Idle:
            handleHeaderLocked(data, length, message, sizeof(message));
            break;
        case State::Receiving:
            handleBodyLocked(data, length, message, sizeof(message));
            break;
        case State::Processing:
            break;
        }
    }
    sendNotify(message);
}

void onDisconnect()
{
    std::lock_guard<std::mutex> lock(gMutex);
    // loop() owns the buffer while Processing, so finish() frees it
    if (gState == State::Receiving)
    {
        resetLocked();
        gError = "disconnected";
    }
}

void poll(uint32_t nowMs)
{
    char message[32] = "";
    {
        std::lock_guard<std::mutex> lock(gMutex);
        if (gState == State::Receiving && nowMs - gLastReceiveMs >= kTimeoutMs)
        {
            failLocked("timeout", message, sizeof(message));
        }
    }
    sendNotify(message);
}

Progress progress()
{
    std::lock_guard<std::mutex> lock(gMutex);
    return Progress{gState, gReceived, gLength};
}

bool takeCompleted(const uint8_t **data, size_t *length, bool *crcOk)
{
    uint32_t expectedCrc;
    {
        std::lock_guard<std::mutex> lock(gMutex);
        if (gState != State::Processing)
        {
            return false;
        }
        *data = gBuffer;
        *length = gLength;
        expectedCrc = gExpectedCrc;
    }
    // The buffer stays unchanged while Processing, so this runs unlocked
    *crcOk = crc32(*data, *length) == expectedCrc;
    return true;
}

void finish(const char *error)
{
    char message[32] = "OK";
    {
        std::lock_guard<std::mutex> lock(gMutex);
        if (gState != State::Processing)
        {
            return;
        }
        if (error)
        {
            failLocked(error, message, sizeof(message));
        }
        else
        {
            resetLocked();
        }
    }
    sendNotify(message);
}

const char *takeError()
{
    std::lock_guard<std::mutex> lock(gMutex);
    const char *error = gError;
    gError = nullptr;
    return error;
}
} // namespace image_receiver
