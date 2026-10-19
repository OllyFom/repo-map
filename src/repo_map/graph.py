"""Approximate call graph.

An edge caller -> callee exists for every call site resolved to a project symbol.
NetworkX is already a dependency:

    import networkx as nx

    graph = nx.DiGraph()
    graph.add_edge("tiny_pkg.a.public_api", "tiny_pkg.b.helper")
    nx.shortest_path(graph, source, target)   # raises nx.NetworkXNoPath
"""

import networkx as nx

from repo_map.model import CallSite


class CallGraph:
    def __init__(self):
        self._graph = nx.DiGraph()

    @classmethod
    def from_call_sites(cls, call_sites: list[CallSite]) -> "CallGraph":
        """Строит граф из списка вызовов.

        Только вызовы с resolution="internal" дают рёбра.
        """
        instance = cls()

        for call_site in call_sites:
            if call_site.resolution == "internal" and call_site.target is not None:
                caller = call_site.scope
                callee = call_site.target
                instance._graph.add_edge(caller, callee)

        return instance

    def callers(self, qualified_name: str) -> list[str]:
        """Возвращает список символов, которые вызывают qualified_name."""
        if qualified_name not in self._graph:
            return []
        return list(self._graph.predecessors(qualified_name))

    def callees(self, qualified_name: str) -> list[str]:
        """Возвращает список символов, которые вызывает qualified_name."""
        if qualified_name not in self._graph:
            return []
        return list(self._graph.successors(qualified_name))

    def shortest_path(self, source: str, target: str) -> list[str] | None:
        """Находит кратчайший путь от source до target.

        Возвращает None, если пути нет.
        """
        try:
            return nx.shortest_path(self._graph, source, target)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None
