from typing import cast

from prometheus_client import REGISTRY, gc_collector, platform_collector, process_collector


def reset_prom_registry() -> None:
    """Resets the Prometheus registry by removing all custom collectors"""

    # Remove all the existing custom collectors from the registry,
    # just leaving behind the standard process collector, platform
    # collector and python garbage collector.
    collectors = list(REGISTRY._collector_to_names.keys())
    for collector in collectors:
        if not isinstance(
            collector,
            (process_collector.ProcessCollector, platform_collector.PlatformCollector, gc_collector.GCCollector),
        ):
            REGISTRY.unregister(collector)


class MetricMonitor:
    """Class to help unit test changes in Prometheus metrics

    Stores the last value of a metric and when the change method is called
    the internal store is updated and the change is returned.
    """

    def __init__(self, name: str, label: dict[str, str] | None = None) -> None:
        """Initialise the monitor.

        Parameters
        ----------
        name : str
            Name of the Prometheus metric.
        labels : dict[str, str] | None, optional
            Label for the Prometheus metric to monitor, e.g., {"my_label": "label_value"}, by default None
        """
        self._name = name
        self._label = label

        if self._get_sample_value() is None:
            raise ValueError(f"Cannot appear to find a metric with {self._name} and label {self._label}")
        self._last_value = cast(float, self._get_sample_value())

    def _get_sample_value(self) -> float | None:
        """Get sample value from the Prometheus registry.

        Returns
        -------
        float | None
        """
        return REGISTRY.get_sample_value(self._name, {} if self._label is None else self._label)

    def change(self) -> float:
        """Get the most recent value of a metric and return the change.

        Returns
        -------
        float
        """
        value = cast(float, self._get_sample_value())
        delta = value - self._last_value
        self._last_value = value

        return delta
