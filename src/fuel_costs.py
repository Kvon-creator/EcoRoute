"""Direct simulated costs alongside the preserved CP2 ML artifact."""
import numpy as np
from src.simulation import assumed_speed, simulated_rate


def directly_simulated_graph(graph):
    """Copy the input; keep routing/UI independent of saved-graph rewrites."""
    result=graph.copy()
    edges=list(result.edges(keys=True,data=True))
    if not edges:
        return result
    x=np.array([[assumed_speed(d.get('highway','unknown')),float(d['grade'])] for *_,d in edges])
    rates=simulated_rate(x)
    for (*_,d),rate in zip(edges,rates):
        length=float(d['length'])
        if not np.isfinite(length) or length<=0:
            raise ValueError('Road length must be finite and positive.')
        d['fuel_liters']=float(rate*length/1000)
    return result
