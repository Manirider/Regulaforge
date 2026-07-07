"""RabbitMQ-based message bus for inter-agent communication.

Provides a publish-subscribe and direct messaging layer for the
multi-agent system using RabbitMQ with aio-pika. Supports message
serialization, delivery acknowledgments, dead letter queues, and
request-response patterns.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any, Optional
from uuid import uuid4

from regulaforge.config.constants import DEFAULT_EXCHANGE, DLQ_SUFFIX, RETRY_SUFFIX
from regulaforge.config.logging import get_logger
from regulaforge.config.settings import settings

logger = get_logger(__name__)


class AgentMessageBus:
    """Message bus for inter-agent communication via RabbitMQ.

    Manages exchanges, queues, and message routing between agents
    with support for direct messaging, broadcasting, subscription,
    and request-response patterns.
    """

    def __init__(self) -> None:
        self._connection = None
        self._channel = None
        self._exchange = None
        self._queues: dict[str, Any] = {}
        self._consumers: dict[str, Any] = {}
        self._response_futures: dict[str, Any] = {}
        self._connected = False
        self._exchange_name = DEFAULT_EXCHANGE

    async def connect(self) -> None:
        """Establish connection to RabbitMQ and declare the exchange.

        Raises:
            RuntimeError: If connection to RabbitMQ fails.
        """
        try:
            import aio_pika

            broker_url = str(settings.broker.url)
            self._connection = await aio_pika.connect_robust(
                broker_url,
                timeout=30,
            )
            self._channel = await self._connection.channel()
            self._channel.prefetch_count = settings.broker.prefetch_count

            self._exchange = await self._channel.declare_exchange(
                name=self._exchange_name,
                type=aio_pika.ExchangeType.TOPIC,
                durable=True,
            )

            await self._declare_dlq()

            self._connected = True
            logger.info(
                "Message bus connected to %s (exchange=%s)",
                broker_url,
                self._exchange_name,
            )
        except ImportError:
            logger.error("aio-pika is not installed. Cannot connect to RabbitMQ.")
            raise RuntimeError("aio-pika package is required for agent message bus")
        except Exception as exc:
            logger.error("Failed to connect to RabbitMQ: %s", exc, exc_info=True)
            raise RuntimeError(f"Failed to connect to message bus: {exc}") from exc

    async def _declare_dlq(self) -> None:
        """Declare dead letter queue and retry queue for failed messages."""
        if not self._channel:
            return


        dlq_name = f"{self._exchange_name}{DLQ_SUFFIX}"
        retry_name = f"{self._exchange_name}{RETRY_SUFFIX}"

        dlq = await self._channel.declare_queue(
            name=dlq_name,
            durable=True,
        )
        await dlq.bind(self._exchange, routing_key=f"*.{DLQ_SUFFIX}")

        retry_queue = await self._channel.declare_queue(
            name=retry_name,
            durable=True,
            arguments={
                "x-dead-letter-exchange": self._exchange_name,
                "x-message-ttl": 60000,
            },
        )
        await retry_queue.bind(self._exchange, routing_key=f"*.{RETRY_SUFFIX}")

        logger.debug("DLQ and retry queues declared: %s, %s", dlq_name, retry_name)

    async def disconnect(self) -> None:
        """Gracefully close the RabbitMQ connection and clean up consumers."""
        for consumer_tag in self._consumers.values():
            try:
                if self._channel:
                    await self._channel.cancel(consumer_tag)
            except Exception as exc:
                logger.warning("Failed to cancel consumer: %s", exc)

        self._consumers.clear()
        self._queues.clear()

        if self._connection:
            try:
                await self._connection.close()
            except Exception as exc:
                logger.warning("Failed to close connection: %s", exc)

        self._connected = False
        logger.info("Message bus disconnected")

    async def send_message(
        self,
        target_agent: str,
        message: dict[str, Any],
    ) -> None:
        """Send a direct message to a specific agent.

        Args:
            target_agent: The target agent type name.
            message: The message payload to send.

        Raises:
            RuntimeError: If the bus is not connected or publish fails.
        """
        if not self._connected or not self._exchange:
            raise RuntimeError("Message bus is not connected")

        try:
            import aio_pika

            routing_key = f"regulaforge.agent.{target_agent}"
            message_bytes = json.dumps(message, default=str).encode("utf-8")

            await self._exchange.publish(
                aio_pika.Message(
                    body=message_bytes,
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                    content_type="application/json",
                    headers={"message_id": str(uuid4())},
                ),
                routing_key=routing_key,
            )
            logger.debug("Message sent to %s (routing_key=%s)", target_agent, routing_key)
        except Exception as exc:
            logger.error("Failed to send message to %s: %s", target_agent, exc)
            raise RuntimeError(f"Failed to send message: {exc}") from exc

    async def broadcast(
        self,
        message_type: str,
        payload: dict[str, Any],
    ) -> None:
        """Broadcast a message to all agents.

        Args:
            message_type: The type/category of the message.
            payload: The message payload.

        Raises:
            RuntimeError: If the bus is not connected or publish fails.
        """
        if not self._connected or not self._exchange:
            raise RuntimeError("Message bus is not connected")

        try:
            import aio_pika

            message_bytes = json.dumps({
                "type": message_type,
                "payload": payload,
                "broadcast": True,
            }, default=str).encode("utf-8")

            await self._exchange.publish(
                aio_pika.Message(
                    body=message_bytes,
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                    content_type="application/json",
                ),
                routing_key="regulaforge.agent.broadcast",
            )
            logger.info("Broadcast sent: type=%s", message_type)
        except Exception as exc:
            logger.error("Failed to broadcast message: %s", exc)
            raise RuntimeError(f"Failed to broadcast: {exc}") from exc

    async def subscribe(
        self,
        agent_type: str,
        handler: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> str:
        """Subscribe an agent to receive messages in its queue.

        Creates a queue named `regulaforge.agent.{agent_type}` and
        binds it to the exchange with the appropriate routing key.

        Args:
            agent_type: The agent type to subscribe.
            handler: An async callable that processes received messages.

        Returns:
            The consumer tag for this subscription.

        Raises:
            RuntimeError: If the bus is not connected or subscription fails.
        """
        if not self._connected or not self._channel:
            raise RuntimeError("Message bus is not connected")

        try:

            queue_name = f"regulaforge.agent.{agent_type}"
            routing_key = queue_name

            queue = await self._channel.declare_queue(
                name=queue_name,
                durable=True,
            )
            await queue.bind(self._exchange, routing_key=routing_key)

            if routing_key not in self._queues:
                self._queues[routing_key] = queue

            consumer_tag = await queue.consume(
                callback=self._create_message_handler(agent_type, handler),
                no_ack=False,
            )
            self._consumers[agent_type] = consumer_tag

            logger.info(
                "Agent subscribed: %s (queue=%s, consumer=%s)",
                agent_type,
                queue_name,
                consumer_tag,
            )
            return consumer_tag
        except Exception as exc:
            logger.error("Failed to subscribe agent %s: %s", agent_type, exc)
            raise RuntimeError(f"Failed to subscribe: {exc}") from exc

    async def request_response(
        self,
        message: dict[str, Any],
        target_agent: str,
        timeout: float = 30.0,
    ) -> Optional[dict[str, Any]]:
        """Send a message and wait for a response (request-response pattern).

        Creates a temporary response queue, sends the message with a
        reply-to header, and waits for the response within the timeout.

        Args:
            message: The request message payload.
            target_agent: The target agent type name.
            timeout: Maximum time to wait for a response in seconds.

        Returns:
            The response message dict, or None if timeout occurs.

        Raises:
            RuntimeError: If the bus is not connected.
        """
        if not self._connected or not self._channel:
            raise RuntimeError("Message bus is not connected")

        try:
            import asyncio

            import aio_pika

            correlation_id = str(uuid4())
            response_queue_name = f"regulaforge.response.{correlation_id}"

            response_queue = await self._channel.declare_queue(
                name=response_queue_name,
                durable=False,
                auto_delete=True,
                exclusive=True,
            )

            future: asyncio.Future = asyncio.get_event_loop().create_future()
            self._response_futures[correlation_id] = future

            consumer_tag = await response_queue.consume(
                callback=self._create_response_handler(correlation_id),
                no_ack=True,
            )

            routing_key = f"regulaforge.agent.{target_agent}"
            message["correlation_id"] = correlation_id
            message["reply_to"] = response_queue_name

            message_bytes = json.dumps(message, default=str).encode("utf-8")
            await self._exchange.publish(
                aio_pika.Message(
                    body=message_bytes,
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                    content_type="application/json",
                    correlation_id=correlation_id,
                    reply_to=response_queue_name,
                ),
                routing_key=routing_key,
            )

            try:
                response = await asyncio.wait_for(future, timeout=timeout)
                return response
            except asyncio.TimeoutError:
                logger.warning(
                    "Request-response timeout: target=%s, timeout=%.1fs",
                    target_agent,
                    timeout,
                )
                self._response_futures.pop(correlation_id, None)
                return None
            finally:
                await self._channel.cancel(consumer_tag)
        except Exception as exc:
            logger.error(
                "Request-response failed: target=%s, error=%s",
                target_agent,
                exc,
            )
            return None

    def _create_message_handler(
        self,
        agent_type: str,
        handler: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> Callable:
        """Create a message handler that deserializes and dispatches messages.

        Args:
            agent_type: The agent type this handler serves.
            handler: The user-provided async handler function.

        Returns:
            A callable suitable for use with queue.consume().
        """
        import aio_pika

        async def message_handler(message: aio_pika.IncomingMessage) -> None:
            async with message.process(ignore_processed=True):
                try:
                    body = json.loads(message.body.decode("utf-8"))
                    logger.debug(
                        "Message received: agent=%s routing_key=%s",
                        agent_type,
                        message.routing_key,
                    )

                    await handler(body)

                    await message.ack()
                except json.JSONDecodeError as exc:
                    logger.error(
                        "Failed to deserialize message for %s: %s",
                        agent_type,
                        exc,
                    )
                    await message.reject(requeue=False)
                except Exception as exc:
                    logger.error(
                        "Handler failed for %s: %s",
                        agent_type,
                        exc,
                        exc_info=True,
                    )
                    if message.redelivered:
                        await message.reject(requeue=False)
                    else:
                        await message.reject(requeue=True)

        return message_handler

    def _create_response_handler(
        self,
        correlation_id: str,
    ) -> Callable:
        """Create a handler for response messages in request-response pattern.

        Args:
            correlation_id: The correlation ID to match responses.

        Returns:
            A callable that resolves the pending future.
        """
        import aio_pika

        async def response_handler(message: aio_pika.IncomingMessage) -> None:
            try:
                body = json.loads(message.body.decode("utf-8"))
                future = self._response_futures.pop(correlation_id, None)
                if future is not None and not future.done():
                    future.set_result(body)
            except Exception as exc:
                logger.error("Response handler error: %s", exc)
                future = self._response_futures.pop(correlation_id, None)
                if future is not None and not future.done():
                    future.set_exception(exc)

        return response_handler

    async def unsubscribe(self, agent_type: str) -> None:
        """Unsubscribe an agent from its message queue.

        Args:
            agent_type: The agent type to unsubscribe.
        """
        consumer_tag = self._consumers.pop(agent_type, None)
        if consumer_tag and self._channel:
            try:
                await self._channel.cancel(consumer_tag)
                logger.info("Agent unsubscribed: %s", agent_type)
            except Exception as exc:
                logger.warning("Failed to unsubscribe %s: %s", agent_type, exc)

    @property
    def is_connected(self) -> bool:
        """Check if the message bus is connected to RabbitMQ."""
        return self._connected
