from __future__ import annotations
import numpy as np

def fast_build_destroy_repair_cache(instance, placement, nodes, placement_cost_cache=None):
    # This accelerator is used only on the path where placement_cost_cache is None.
    if placement_cost_cache is not None:
        from certified_assignment.destroy_repair_analysis import build_destroy_repair_cache as orig
        return orig(instance, placement, nodes, placement_cost_cache=placement_cost_cache)
    from certified_assignment.destroy_repair_analysis import DestroyRepairCache, normalize_destroy_nodes
    from certified_assignment.feasibility import resource_usage
    p=instance.validate_placement(placement)
    destroy=normalize_destroy_nodes(instance,nodes)
    k,m=len(destroy),instance.n_hosts
    da=np.asarray(destroy,dtype=int)
    mask=np.zeros(instance.n_nodes,dtype=bool); mask[da]=True
    fixed=np.flatnonzero(~mask)
    usage=resource_usage(instance,p)
    residual=instance.capacities-usage
    for node in destroy:
        residual[p[node]] += instance.demands[node]
    external=np.zeros((k,m),dtype=float)
    for a,node in enumerate(destroy):
        old_host=int(p[node])
        if fixed.size==0: continue
        fh=p[fixed]
        out_w=instance.interaction[node,fixed]
        in_w=instance.interaction[fixed,node]
        old_external=float(np.sum(out_w*instance.host_cost[old_host,fh]) + np.sum(in_w*instance.host_cost[fh,old_host]))
        # Preserve per-host np.sum operations exactly; only pair_gain is vectorized below.
        for host in range(m):
            new_external=float(np.sum(out_w*instance.host_cost[host,fh]) + np.sum(in_w*instance.host_cost[fh,host]))
            external[a,host]=old_external-new_external
    pair=np.zeros((k,k,m,m),dtype=float)
    hc=instance.host_cost
    hct=hc.T
    for a in range(k):
        i=destroy[a]; oi=int(p[i])
        for b in range(a+1,k):
            j=destroy[b]; oj=int(p[j])
            wij=instance.interaction[i,j]; wji=instance.interaction[j,i]
            old_pair=wij*hc[oi,oj] + wji*hc[oj,oi]
            pair[a,b,:,:]=old_pair - (wij*hc + wji*hct)
    return DestroyRepairCache(nodes=destroy,original_hosts=p[da].copy(),residual_capacity=residual,external_gain=external,pair_gain=pair)

def install():
    import certified_assignment.paper2_online_pilot as p7
    p7.build_destroy_repair_cache = fast_build_destroy_repair_cache
