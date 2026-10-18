#pragma once

#include <cstddef>
#include <cstdint>

// Receiver state machine of the image transfer protocol
// (docs/protocol.md §4). Call onReceive / onDisconnect from the NimBLE host
// task and everything else from loop().
namespace image_receiver
{
enum class State
{
    Idle,
    Receiving,
    Processing,
};

struct Progress
{
    State state;
    uint32_t received;
    uint32_t length;
};

using NotifyFunction = void (*)(const char *message);

void begin(NotifyFunction notify);

// Called from the NimBLE host task
void onReceive(const uint8_t *data, size_t length);
void onDisconnect();

// Called from loop()
void poll(uint32_t nowMs);
Progress progress();

// Returns the body once received (Processing) and stores the CRC32 check
// result in crcOk
bool takeCompleted(const uint8_t **data, size_t *length, bool *crcOk);

// End Processing. Notifies OK if error is nullptr, ERR <error> otherwise
void finish(const char *error);

// Returns the error reason raised since the last call (nullptr if none)
const char *takeError();
} // namespace image_receiver
