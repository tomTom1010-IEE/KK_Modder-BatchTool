"""Conservative suggestions from original weights and mesh connectivity.

No learned classifier, no physics/role inference, and no automatic approval.
Thresholds apply to normalized effective body/dynamic shares, not raw weights.
"""
from collections import deque
from statistics import mean, median, pvariance
from math import sqrt, isfinite

VERSION = 1


def percentile(values, q):
    a = sorted(values); p = (len(a)-1)*q; i = int(p)
    return a[i] + (a[min(i+1,len(a)-1)]-a[i])*(p-i)


def suggest_pattern(rows, edges, body_bones, dynamic_bones, vertices, ignored=()):
    body=set(body_bones); dynamic=set(dynamic_bones); ignored=set(ignored)
    ids=set(vertices); report={'version':VERSION,'mode':'REVIEW','count':len(ids),'components':[]}
    def reject(reason):
        report['reason']=reason
        return report
    if body & dynamic:return reject('Body and dynamic roles conflict')
    if len(ids)<8:return reject('Too few valid samples; manual review required')
    if any(type(i) is not int or not 0<=i<len(rows) for i in ids):return reject('Invalid vertex scope')
    adj=[set() for _ in rows]
    for a,b in edges:adj[a].add(b);adj[b].add(a)
    needed=ids|{j for i in ids for j in adj[i]}
    shares={}; perbone={}
    for i in needed:
        row=rows[i]
        if any(not isfinite(w) or w<0 for w in row.values()):return reject('Invalid weights detected')
        if any(w>1e-8 and n not in body|dynamic|ignored for n,w in row.items()):return reject('Region or adjacent boundary has weights with unknown ownership')
        total=sum(w for n,w in row.items() if n in body|dynamic)
        if total<=1e-8:return reject('Region or adjacent boundary lacks valid weights')
        perbone[i]={n:row.get(n,0)/total for n in body if row.get(n,0)>0}
        shares[i]=sum(perbone[i].values())
    values=[shares[i] for i in ids];avg=mean(values)
    report['statistics']={'mean':avg,'variance':pvariance(values),'min':min(values),'max':max(values),
        'range':max(values)-min(values),'relative_range':(max(values)-min(values))/max(avg,1e-6),
        'p05':percentile(values,.05),'p95':percentile(values,.95)}
    unseen=set(ids)
    while unseen:
        seed=min(unseen);unseen.remove(seed);component={seed};queue=[seed]
        for i in queue:
            for j in adj[i]&unseen:unseen.remove(j);component.add(j);queue.append(j)
        result=_component(component,adj,shares,perbone)
        report['components'].append(result)
    modes={x['mode'] for x in report['components'] if not x.get('zero_body')}
    if not modes:return reject('Dynamic-only region has no body-follow mode; retain zero body budget')
    if len(modes)!=1 or 'REVIEW' in modes:return reject('Component modes disagree or evidence is insufficient; review per component or vertex')
    report['mode']=next(iter(modes))
    report['reason']='Body share and internal bone distribution are stable' if report['mode']=='UNIFORM' else 'Body influence decays with topological distance from the attachment boundary'
    return report


def _component(ids,adj,shares,perbone):
    out={'mode':'REVIEW','count':len(ids)}
    def reject(reason):out['reason']=reason;return out
    values=[shares[i] for i in ids];avg=mean(values);span=max(values)-min(values)
    if max(values)<=1e-6:
        out['zero_body']=True
        return reject('Dynamic-only components retain zero body budget and do not vote on mode')
    if len(ids)<6:return reject('Insufficient samples in a disconnected component')
    names={n for i in ids for n in perbone[i]}
    # Total-variation distance checks the internal BODY distribution too.
    distributions={i:{n:perbone[i].get(n,0)/max(shares[i],1e-8) for n in names} for i in ids}
    center={n:mean(distributions[i][n] for i in ids) for n in names}
    variation=[sum(abs(distributions[i][n]-center[n]) for n in names)/2 for i in ids]
    out['internal_variation_p95']=percentile(variation,.95)
    if span<=.025 and span/max(avg,1e-6)<=.20 and percentile(variation,.95)<=.08 and max(variation)<=.18:
        out['mode']='UNIFORM';return out
    # A stable per-bone pedestal plus a changing contribution is the reserved
    # mixed-component case. Do not call it an ordinary edge gradient.
    stable=[];changing=[]
    for n in names:
        weights=[perbone[i].get(n,0) for i in ids];delta=max(weights)-min(weights)
        if min(weights)>=.03 and delta<=max(.015,.15*mean(weights)):stable.append(n)
        if delta>=.10:changing.append(n)
    if stable and changing:
        out['stable_components']=sorted(stable)
        return reject('Stable and graded body components are combined; not covered by the current algorithm')
    if span<.15 or min(values)>.12 or max(values)<.20:return reject('No clear free-end decay, or a persistent body-follow component exists')
    # Seeds must touch body-dominated vertices outside this influence mask.
    seeds={i for i in ids if any(j not in ids and shares.get(j,0)>=.90 and shares[j]>shares[i]+.01 for j in adj[i])}
    if not seeds:return reject('No adjacent body-dominated attachment boundary found')
    dist={i:0 for i in seeds};q=deque(seeds)
    while q:
        i=q.popleft()
        for j in adj[i]&ids:
            if j not in dist:dist[j]=dist[i]+1;q.append(j)
    levels=max(dist.values())
    if len(dist)!=len(ids) or levels<3:return reject('Insufficient topological distance layers')
    ds=[dist[i] for i in ids];dm=mean(ds);vm=mean(values)
    numerator=sum((dist[i]-dm)*(shares[i]-vm) for i in ids)
    denominator=sqrt(sum((d-dm)**2 for d in ds)*sum((v-vm)**2 for v in values))
    correlation=numerator/denominator if denominator else 0
    links=[(i,j) for i in ids for j in adj[i]&ids if dist[j]>dist[i]]
    reverse=sum(shares[j]>shares[i]+max(.015,.05*span) for i,j in links)/max(1,len(links))
    layer_means=[mean(shares[i] for i in ids if dist[i]==d) for d in range(levels+1)]
    # Weighted decreasing isotonic regression: unlike linear correlation this
    # accepts a narrow attachment falloff followed by a long zero-weight tail.
    blocks=[]
    for d,value in enumerate(layer_means):
        count=sum(dist[i]==d for i in ids);blocks.append(([d],value*count,count))
        while len(blocks)>1 and blocks[-2][1]/blocks[-2][2]<blocks[-1][1]/blocks[-1][2]:
            b=blocks.pop();a=blocks.pop();blocks.append((a[0]+b[0],a[1]+b[1],a[2]+b[2]))
    fitted={d:total/count for ds,total,count in blocks for d in ds}
    variance=sum((shares[i]-vm)**2 for i in ids)
    monotonic_r2=1-sum((shares[i]-fitted[dist[i]])**2 for i in ids)/max(variance,1e-12)
    out.update(distance_correlation=correlation,reverse_edge_fraction=reverse,layers=levels+1,
               monotonic_r2=monotonic_r2,first_layer_mean=layer_means[0],last_layer_mean=layer_means[-1])
    if monotonic_r2<.65 or reverse>.10 or layer_means[0]-layer_means[-1]<.6*span:
        return reject('Variation does not follow attachment-boundary distance; gradient classification is unreliable')
    neighbor_steps=[abs(shares[i]-shares[j])/span for i,j in links]
    if percentile(neighbor_steps,.95)>.60:return reject('Local jumps are too large; insufficient evidence of a continuous gradient')
    out['mode']='EDGE_GRADIENT';return out
