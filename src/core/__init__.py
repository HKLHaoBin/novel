"""核心模块"""

from .character import Ability, CharacterCard
from .coordinator import NovelContext, NovelCoordinator
from .graph import Edge, EdgeType, Graph, Node, NodeType, TimePoint, Timeline
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
    # Graph
    "Graph", "Node", "NodeType", "Edge", "EdgeType", "TimePoint", "Timeline",
    # Character
    "CharacterCard", "Ability",
    # Map
    "Location", "LocationEdge", "LocationRelation", "LocationType", "WorldMap",
    # State
    "GenerationPhase", "GenerationProgress", "ChapterStatus",
    "AgentSnapshot", "NovelSnapshot", "NovelStateManager",
    # Coordinator
    "NovelContext", "NovelCoordinator",
]
