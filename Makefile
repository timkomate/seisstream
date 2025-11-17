CC = cc
CFLAGS = -O2 -g -Wall -Wextra -Wpedantic -std=c11

SRC = connector/src/connector.c
BUILD_DIR = build
TARGET = $(BUILD_DIR)/connector

LIBS = -lslink -lrabbitmq

.PHONY: all clean

all: $(TARGET)

$(TARGET): $(SRC) | $(BUILD_DIR)
	$(CC) $(CFLAGS) $< $(LIBS) -o $@

$(BUILD_DIR):
	mkdir -p $@

clean:
	rm -rf $(BUILD_DIR)
