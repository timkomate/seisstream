CC = cc
CFLAGS = -O2 -g -Wall -Wextra -Wpedantic -std=c11
CPPFLAGS = -Iconnector/include

SRCS = connector/src/connector.c \
       connector/src/cli.c \
       connector/src/auth.c \
       connector/src/amqp_client.c

BUILD_DIR = build
TARGET = $(BUILD_DIR)/connector

LIBS = -lslink -lrabbitmq

.PHONY: all clean

all: $(TARGET)

$(TARGET): $(SRCS) | $(BUILD_DIR)
	$(CC) $(CPPFLAGS) $(CFLAGS) $(SRCS) $(LIBS) -o $@

$(BUILD_DIR):
	mkdir -p $@

clean:
	rm -rf $(BUILD_DIR)
