"""Distance helper.

Re-exported from the shared contracts package so the agent's walkability
reasoning and the MCP server's route estimates cannot drift apart.
"""

from saas_contracts.geo import haversine_km as distance_km

__all__ = ["distance_km"]
