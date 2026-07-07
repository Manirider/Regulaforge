"""Production dependency injection container.

Provides a type-safe, async-capable DI container with three lifetime
scopes (singleton, transient, scoped), factory support, and FastAPI
integration — all without third-party DI libraries.

Usage::

    from regulaforge.config.container import Container, Lifetime

    container = Container()
    container.register(IRepository, SqlAlchemyRepository, Lifetime.SINGLETON)
    container.register_factory(ICache, redis_cache_factory, Lifetime.SINGLETON)

    # Resolve
    repo = await container.resolve(IRepository)

    # FastAPI integration
    @app.get("/items")
    async def list_items(c: Container = Depends(get_container)):
        repo = await c.resolve(IRepository)
        ...

    # Scoped lifetime (per-request)
    async with container.create_scope() as scope:
        uow = await scope.resolve(IUnitOfWork)
        ...

    # Testing overrides
    container.override(IRepository, FakeRepository)
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import threading
from collections.abc import Awaitable, Callable
from enum import Enum, auto
from typing import Any, Optional, TypeVar, get_type_hints

T = TypeVar("T")

logger = logging.getLogger("regulaforge.config.container")


class Lifetime(Enum):
    """Service lifetime scope."""

    SINGLETON = auto()
    """One instance per container, created on first resolve."""

    TRANSIENT = auto()
    """New instance on every resolve call."""

    SCOPED = auto()
    """One instance per scope (e.g. per HTTP request)."""


class _Registration:
    """Internal registration record."""

    __slots__ = (
        "interface",
        "implementation",
        "factory",
        "lifetime",
        "instance",
    )

    def __init__(
        self,
        interface: type,
        implementation: Optional[type] = None,
        factory: Optional[Callable[..., Any]] = None,
        lifetime: Lifetime = Lifetime.TRANSIENT,
    ) -> None:
        self.interface = interface
        self.implementation = implementation
        self.factory = factory
        self.lifetime = lifetime
        self.instance: Any = None


class Container:
    """Async-capable dependency injection container.

    Supports three lifetime scopes:

    * **Singleton** — One instance shared across the container.
    * **Transient** — New instance on every ``resolve()`` call.
    * **Scoped** — One instance per ``create_scope()`` context.

    Thread-safe for registration; async-safe for resolution.
    """

    def __init__(self, parent: Optional[Container] = None) -> None:
        self._registrations: dict[type, _Registration] = {}
        self._overrides: dict[type, _Registration] = {}
        self._scoped_instances: dict[type, Any] = {}
        self._parent = parent
        self._lock = threading.Lock()
        self._is_scope = parent is not None

    # ─── Registration ───────────────────────────────────────────────────

    def register(
        self,
        interface: type[T],
        implementation: type[T],
        lifetime: Lifetime = Lifetime.TRANSIENT,
    ) -> Container:
        """Register an interface→implementation mapping.

        Args:
            interface: The abstract type or protocol to register.
            implementation: The concrete class that implements it.
            lifetime: The lifetime scope for instances.

        Returns:
            Self for fluent chaining.
        """
        with self._lock:
            self._registrations[interface] = _Registration(
                interface=interface,
                implementation=implementation,
                lifetime=lifetime,
            )
        logger.debug(
            "Registered %s → %s [%s]",
            interface.__name__,
            implementation.__name__,
            lifetime.name,
        )
        return self

    def register_instance(
        self,
        interface: type[T],
        instance: T,
    ) -> Container:
        """Register a pre-created instance as a singleton.

        Args:
            interface: The abstract type or protocol.
            instance: The pre-created instance.

        Returns:
            Self for fluent chaining.
        """
        with self._lock:
            reg = _Registration(
                interface=interface,
                lifetime=Lifetime.SINGLETON,
            )
            reg.instance = instance
            self._registrations[interface] = reg
        logger.debug(
            "Registered instance for %s",
            interface.__name__,
        )
        return self

    def register_factory(
        self,
        interface: type[T],
        factory: Callable[..., T | Awaitable[T]],
        lifetime: Lifetime = Lifetime.TRANSIENT,
    ) -> Container:
        """Register an interface with a factory function.

        The factory can be sync or async. It receives the container
        as its first argument for resolving sub-dependencies.

        Args:
            interface: The abstract type or protocol.
            factory: Callable that creates the instance.
            lifetime: The lifetime scope for instances.

        Returns:
            Self for fluent chaining.
        """
        with self._lock:
            self._registrations[interface] = _Registration(
                interface=interface,
                factory=factory,
                lifetime=lifetime,
            )
        logger.debug(
            "Registered factory for %s [%s]",
            interface.__name__,
            lifetime.name,
        )
        return self

    # ─── Overrides (testing) ────────────────────────────────────────────

    def override(
        self,
        interface: type[T],
        implementation: type[T] | None = None,
        *,
        instance: T | None = None,
        factory: Callable[..., T | Awaitable[T]] | None = None,
    ) -> Container:
        """Override a registration for testing.

        Overrides take priority over registrations. Call
        ``clear_overrides()`` to restore original registrations.

        Args:
            interface: The type to override.
            implementation: Override implementation class.
            instance: Override with a pre-created instance.
            factory: Override with a factory.

        Returns:
            Self for fluent chaining.
        """
        with self._lock:
            if instance is not None:
                reg = _Registration(
                    interface=interface,
                    lifetime=Lifetime.SINGLETON,
                )
                reg.instance = instance
            elif factory is not None:
                reg = _Registration(
                    interface=interface,
                    factory=factory,
                    lifetime=Lifetime.TRANSIENT,
                )
            elif implementation is not None:
                reg = _Registration(
                    interface=interface,
                    implementation=implementation,
                    lifetime=Lifetime.TRANSIENT,
                )
            else:
                raise ValueError(
                    "override() requires implementation, instance, or factory"
                )
            self._overrides[interface] = reg
        return self

    def clear_overrides(self) -> None:
        """Remove all test overrides, restoring original registrations."""
        with self._lock:
            self._overrides.clear()

    # ─── Resolution ─────────────────────────────────────────────────────

    async def resolve(self, interface: type[T]) -> T:
        """Resolve an instance for the given interface.

        Resolution order:
        1. Overrides (if any)
        2. Scoped instances (if in a scope)
        3. Singleton instances (cached)
        4. Factory or constructor auto-wiring

        Args:
            interface: The type to resolve.

        Returns:
            An instance of the requested type.

        Raises:
            KeyError: If no registration exists for the interface.
        """
        # Check overrides first
        reg = self._overrides.get(interface)
        if reg is None:
            reg = self._registrations.get(interface)
        if reg is None and self._parent is not None:
            return await self._parent.resolve(interface)
        if reg is None:
            raise KeyError(
                f"No registration found for {interface.__name__}. "
                f"Registered types: {[t.__name__ for t in self._registrations]}"
            )

        # Return cached singleton
        if reg.lifetime == Lifetime.SINGLETON and reg.instance is not None:
            return reg.instance

        # Return cached scoped instance
        if reg.lifetime == Lifetime.SCOPED:
            if not self._is_scope:
                raise KeyError(
                    f"Cannot resolve scoped service {interface.__name__} from "
                    f"root container. You must resolve scoped services from a scope."
                )
            if interface in self._scoped_instances:
                return self._scoped_instances[interface]

        # Create instance
        instance = await self._create_instance(reg)

        # Cache per lifetime
        if reg.lifetime == Lifetime.SINGLETON:
            reg.instance = instance
        elif reg.lifetime == Lifetime.SCOPED and self._is_scope:
            self._scoped_instances[interface] = instance

        return instance

    def resolve_sync(self, interface: type[T]) -> T:
        """Synchronous resolve for startup/configuration contexts.

        Only works for registrations with pre-created instances
        (singletons that have already been resolved or registered
        via ``register_instance``).

        Args:
            interface: The type to resolve.

        Returns:
            The cached instance.

        Raises:
            KeyError: If no registration or cached instance exists.
            RuntimeError: If the registration requires async creation.
        """
        reg = self._overrides.get(interface) or self._registrations.get(interface)
        if reg is None:
            raise KeyError(f"No registration found for {interface.__name__}")
        if reg.instance is not None:
            return reg.instance
        raise RuntimeError(
            f"Cannot synchronously resolve {interface.__name__}. "
            f"Use 'await container.resolve()' or register an instance."
        )

    async def _create_instance(self, reg: _Registration) -> Any:
        """Create an instance from a registration."""
        # Factory-based creation
        if reg.factory is not None:
            result = reg.factory(self)
            if asyncio.iscoroutine(result) or asyncio.isfuture(result):
                return await result
            return result

        # Constructor auto-wiring
        if reg.implementation is not None:
            return await self._auto_wire(reg.implementation)

        raise RuntimeError(
            f"Registration for {reg.interface.__name__} has no "
            f"implementation or factory"
        )

    async def _auto_wire(self, cls: type[T]) -> T:
        """Auto-wire constructor dependencies via type annotations.

        Inspects the ``__init__`` signature and resolves each
        annotated parameter from the container. Parameters with
        defaults are used as-is if not registered.
        """
        if cls.__init__ is object.__init__:
            return cls()

        try:
            hints = get_type_hints(cls.__init__)
        except Exception:
            hints = {}

        sig = inspect.signature(cls.__init__)
        kwargs: dict[str, Any] = {}

        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue

            # Ignore variable positional/keyword parameters (*args, **kwargs)
            if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                continue

            param_type = hints.get(param_name)
            if param_type is None:
                if param.default is not inspect.Parameter.empty:
                    continue
                raise TypeError(
                    f"Cannot auto-wire parameter '{param_name}' of "
                    f"{cls.__name__}: no type annotation"
                )

            # Skip built-in types and Optional wrappers
            origin = getattr(param_type, "__origin__", None)
            if param_type in (str, int, float, bool, bytes, dict, list, set, tuple):
                if param.default is not inspect.Parameter.empty:
                    continue
                raise TypeError(
                    f"Cannot auto-wire primitive parameter '{param_name}' "
                    f"of {cls.__name__}"
                )

            # Handle Optional[X] — extract inner type
            if origin is not None:
                args = getattr(param_type, "__args__", ())
                # Union[X, None] pattern (Optional)
                if type(None) in args:
                    inner_types = [a for a in args if a is not type(None)]
                    if len(inner_types) == 1:
                        param_type = inner_types[0]
                    else:
                        if param.default is not inspect.Parameter.empty:
                            continue
                        raise TypeError(
                            f"Cannot auto-wire Union parameter '{param_name}' "
                            f"of {cls.__name__}"
                        )
                else:
                    if param.default is not inspect.Parameter.empty:
                        continue
                    raise TypeError(
                        f"Cannot auto-wire generic parameter '{param_name}' "
                        f"of {cls.__name__}"
                    )

            # Try to resolve from container
            try:
                kwargs[param_name] = await self.resolve(param_type)
            except (KeyError, TypeError):
                if param.default is not inspect.Parameter.empty:
                    continue
                raise

        return cls(**kwargs)

    # ─── Scoping ────────────────────────────────────────────────────────

    def create_scope(self) -> _ContainerScope:
        """Create a scoped child container for per-request lifetime.

        Usage::

            async with container.create_scope() as scope:
                uow = await scope.resolve(IUnitOfWork)
                ...

        Returns:
            An async context manager yielding a scoped Container.
        """
        return _ContainerScope(self)

    # ─── Introspection ──────────────────────────────────────────────────

    def is_registered(self, interface: type) -> bool:
        """Check if a type is registered."""
        return (
            interface in self._registrations
            or interface in self._overrides
            or (self._parent is not None and self._parent.is_registered(interface))
        )

    @property
    def registered_types(self) -> list[str]:
        """List of registered type names."""
        types = set(t.__name__ for t in self._registrations)
        if self._parent:
            types.update(self._parent.registered_types)
        return sorted(types)

    def __repr__(self) -> str:
        scope_label = "scope" if self._is_scope else "root"
        return (
            f"Container({scope_label}, "
            f"registrations={len(self._registrations)}, "
            f"overrides={len(self._overrides)})"
        )


class _ContainerScope:
    """Async context manager for scoped container lifetime."""

    def __init__(self, parent: Container) -> None:
        self._parent = parent
        self._scope: Optional[Container] = None

    async def __aenter__(self) -> Container:
        self._scope = Container(parent=self._parent)
        # Copy parent registrations into scope so scoped instances work
        self._scope._registrations = dict(self._parent._registrations)
        self._scope._overrides = dict(self._parent._overrides)
        return self._scope

    async def __aexit__(
        self,
        exc_type: type | None,
        exc_val: Exception | None,
        exc_tb: object | None,
    ) -> None:
        if self._scope is not None:
            # Clean up scoped instances
            for instance in self._scope._scoped_instances.values():
                close = getattr(instance, "close", None)
                if close and callable(close):
                    try:
                        result = close()
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception:
                        logger.warning(
                            "Error closing scoped instance %s",
                            type(instance).__name__,
                            exc_info=True,
                        )
            self._scope._scoped_instances.clear()
            self._scope = None


# ─── Global container and FastAPI integration ────────────────────────────

_global_container: Optional[Container] = None
_container_lock = threading.Lock()


def get_global_container() -> Container:
    """Get or create the global DI container.

    Returns:
        The global Container singleton.
    """
    global _global_container
    if _global_container is None:
        with _container_lock:
            if _global_container is None:
                _global_container = Container()
    return _global_container


def set_global_container(container: Container) -> None:
    """Replace the global DI container (for testing).

    Args:
        container: The container to use as global.
    """
    global _global_container
    with _container_lock:
        _global_container = container


async def get_container() -> Container:
    """FastAPI dependency that provides the DI container.

    Usage::

        @router.get("/items")
        async def list_items(
            container: Container = Depends(get_container),
        ):
            repo = await container.resolve(IRegulationRepository)
            ...
    """
    return get_global_container()


__all__ = [
    "Container",
    "Lifetime",
    "get_global_container",
    "set_global_container",
    "get_container",
]
