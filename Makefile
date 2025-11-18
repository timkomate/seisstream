CC = cc
CFLAGS = -O2 -g -Wall -Wextra -Wpedantic -std=c11
CPPFLAGS = -Iconnector/include -Iconsumer/include

BUILD_DIR = build

CONNECTOR_SRCS = connector/src/connector.c \
                 connector/src/cli.c \
                 connector/src/auth.c \
                 connector/src/amqp_client.c
CONNECTOR_TARGET = $(BUILD_DIR)/connector
CONNECTOR_LIBS = -lslink -lrabbitmq

CONSUMER_SRCS = consumer/src/consumer.c \
                consumer/src/cli.c \
                consumer/src/mseed.c \
                consumer/src/pg_client.c
CONSUMER_TARGET = $(BUILD_DIR)/consumer
CONSUMER_LIBS = -lrabbitmq -lmseed -lpq

TARGETS = $(CONNECTOR_TARGET) $(CONSUMER_TARGET)

.PHONY: all clean connector consumer

all: $(TARGETS)

connector: $(CONNECTOR_TARGET)

consumer: $(CONSUMER_TARGET)

$(CONNECTOR_TARGET): $(CONNECTOR_SRCS) | $(BUILD_DIR)
	$(CC) $(CPPFLAGS) $(CFLAGS) $(CONNECTOR_SRCS) $(CONNECTOR_LIBS) -o $@

$(CONSUMER_TARGET): $(CONSUMER_SRCS) | $(BUILD_DIR)
	$(CC) $(CPPFLAGS) $(CFLAGS) $(CONSUMER_SRCS) $(CONSUMER_LIBS) -o $@

$(BUILD_DIR):
	mkdir -p $@

clean:
	rm -rf $(BUILD_DIR)
