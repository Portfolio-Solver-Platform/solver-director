import logging
import aio_pika

logger = logging.getLogger(__name__)

RETRY_DELAYS = [5, 30, 60]


async def declare_quorum_queue(channel, name: str) -> aio_pika.abc.AbstractQueue:
    queue = await channel.declare_queue(name, durable=True, arguments={"x-queue-type": "quorum"})
    for delay in RETRY_DELAYS:
        await channel.declare_queue(
            f"{name}.retry.{delay}s",
            durable=True,
            arguments={
                "x-queue-type": "quorum",
                "x-message-ttl": delay * 1000,
                "x-dead-letter-exchange": "",
                "x-dead-letter-routing-key": name,
            },
        )
    await channel.declare_queue(f"{name}.dlq", durable=True, arguments={"x-queue-type": "quorum"})
    return queue


async def retry_or_dlq(channel, queue_name: str, message: aio_pika.abc.AbstractIncomingMessage, exc: Exception):
    attempt = int((message.headers or {}).get("x-attempt", 0))
    headers = {**dict(message.headers or {}), "x-attempt": attempt + 1}

    if attempt < len(RETRY_DELAYS):
        delay = RETRY_DELAYS[attempt]
        routing_key = f"{queue_name}.retry.{delay}s"
        logger.warning(f"Retrying message (attempt {attempt + 1}/{len(RETRY_DELAYS)}, delay {delay}s): {exc}")
    else:
        routing_key = f"{queue_name}.dlq"
        logger.error(f"Message failed after {len(RETRY_DELAYS)} attempts, routing to DLQ: {exc}")

    try:
        await channel.default_exchange.publish(
            aio_pika.Message(
                body=message.body,
                headers=headers,
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=routing_key,
        )
        await message.ack()
    except Exception:
        logger.exception("Failed to publish to retry/DLQ, requeueing original message")
        await message.nack(requeue=True)
