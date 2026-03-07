"""核心模块"""

from .character import Ability, CharacterCard
from .coordinator import NovelContext, NovelCoordinator
from .graph import Edge, EdgeType, Graph, Node, NodeType, Timeline, TimePoint
from .map import Location, LocationEdge, LocationRelation, LocationType, WorldMap
from .state import (
    AgentSnapshot,
    ChapterStatus,
    GenerationPhase,
    GenerationProgress,
    NovelSnapshot,
    NovelStateManager,
)

__all__ = [
    "Ability",
    "AgentSnapshot",
    "ChapterStatus",
    # Character
    "CharacterCard",
    "Edge",
    "EdgeType",
    # State
    "GenerationPhase",
    "GenerationProgress",
    # Graph
    "Graph",
    # Map
    "Location",
    "LocationEdge",
    "LocationRelation",
    "LocationType",
    "Node",
    "NodeType",
    # Coordinator
    "NovelContext",
    "NovelCoordinator",
    "NovelSnapshot",
    "NovelStateManager",
    "TimePoint",
    "Timeline",
    "WorldMap",
]
