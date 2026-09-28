"""Total-support constraints shared by garment and shoe workflows (NumPy only).

Absent policy means the historical unlimited behaviour. Support selection is a
bounded discrete search; continuous solvers subsequently freeze that support.
No result is silently truncated, including tiny positive category budgets.
"""
import itertools
import numpy as np


def policy(value=None):
    value = value or {}
    if value.get('count_threshold',0.)!=0 or value.get('export_dtype','float32')!='float32':
        raise ValueError('Only strict positive counting and float32 writeback are supported')
    limit = value.get('max_influences', 0)
    if isinstance(limit, bool) or limit not in (0, 4):
        raise ValueError('Total influence limit must be 0 (unlimited) or 4')
    tolerance = float(value.get('dynamic_error_limit', .002))
    if not np.isfinite(tolerance) or tolerance <= 0:
        raise ValueError('Invalid dynamic response tolerance')
    return dict(schema=1, max_influences=int(limit),
                compress_dynamic=bool(value.get('compress_dynamic', False)),
                dynamic_error_limit=tolerance, count_threshold=0., export_dtype='float32')


def audit(weights, value=None):
    """Count final unique bone columns; ancestors and categories are not slots."""
    p = policy(value); w = np.asarray(weights, float)
    if w.ndim != 2 or not np.isfinite(w).all() or np.any(w < 0):
        raise ValueError('Invalid influence matrix')
    counts = (w > 0).sum(1)
    exported = (w.astype(np.float32) > 0).sum(1)
    over = np.flatnonzero(counts > p['max_influences']) if p['max_influences'] else np.array([], int)
    return dict(policy=p, maximum=int(counts.max(initial=0)),
                export_maximum=int(exported.max(initial=0)), over_limit_vertices=over.tolist(),
                representation=('UNLIMITED' if not p['max_influences'] else
                                'RUNTIME_REVIEW_REQUIRED' if len(over) else 'STRICT_FOUR'),
                strict_compatible=bool(p['max_influences'] and not len(over)),
                runtime_validation='NOT_TESTED')


def _project(x, mass, lower=None, upper=None):
    """Euclidean simplex projection, optionally with local correction bounds."""
    if mass == 0: return np.zeros_like(x)
    if lower is None:
        u = np.sort(x)[::-1]; cs = np.cumsum(u)-mass
        ids = np.flatnonzero(u-cs/np.arange(1, len(u)+1) > 0)
        return np.maximum(x-cs[ids[-1]]/(ids[-1]+1), 0)
    if lower.sum() > mass+1e-10 or upper.sum() < mass-1e-10:
        return None
    lo = float(np.min(x-upper)); hi = float(np.max(x-lower))
    for _ in range(48):
        mid = (lo+hi)/2
        if np.clip(x-mid, lower, upper).sum() > mass: lo = mid
        else: hi = mid
    return np.clip(x-(lo+hi)/2, lower, upper)


def _fit(support, original, frozen, regions, budgets, h, rhs, limit):
    """Small feasible QP used for support ranking, not final global fitting."""
    ids = np.asarray(sorted(support), int)
    out = frozen.copy()
    missing = np.ones(len(original), bool); missing[ids] = False
    if np.any(abs(out[missing]-original[missing]) > limit+1e-10): return None
    if not len(ids):
        return out if np.max(abs(np.bincount(regions, weights=out, minlength=len(budgets))-budgets)) < 1e-6 else None
    a = original[ids]; low = np.maximum(0, a-limit); high = np.minimum(1, a+limit)
    groups = []
    for r, budget in enumerate(budgets):
        js = np.flatnonzero(regions[ids] == r)
        mass = budget-frozen[regions == r].sum()
        if not len(js):
            # Source budgets are float64; Blender fixed weights round to float32.
            # A positive *free* category is checked by evaluate before this call.
            if abs(mass)>1e-6:return None
            continue
        if mass < -1e-6:return None
        if len(js): groups.append((js, max(0., mass)))
    def project(x):
        result = x.copy()
        for js, mass in groups:
            v = _project(x[js], mass, low[js], high[js]) if limit < 1 else _project(x[js], mass)
            if v is None: return None
            result[js] = v
        return result
    x = project(a)
    if x is None: return None
    hh = h[np.ix_(ids, ids)]; r = rhs[ids] - h[ids] @ frozen
    step = 1 / max(float(np.abs(hh).sum(1).max()), 1e-12)
    for _ in range(32 if len(ids) <= 4 else 12):
        y = project(x-step*(hh@x-r))
        if np.max(abs(y-x)) < 1e-10: x = y; break
        x = y
    out[ids] = x
    return out


def _dynamic_error(rest, delta, matrices, scale):
    if matrices is None or not len(matrices): return float('inf')
    ids = np.flatnonzero(delta)
    if not len(ids): return 0.
    local=matrices[:, ids]
    basis = np.einsum('pbij,j->pbi', local[..., :3, :3], rest) + local[..., :3, 3]
    return float(np.linalg.norm(np.einsum('b,pbc->pc', delta[ids], basis), axis=1).max()/scale)


def select(initial, regions, budgets, fixed, allowed, value=None, *, selected=None,
           delta_limits=None, rest=None, matrices=None, reference=None, pose_weights=None,
           prior=.02, dynamic_train=None, dynamic_scale=1., objective=None, weight_prior=None):
    """Select <=4 total bones or preserve and report an infeasible vertex.

    The outer search evaluates feasible regional fits, not weight-only top-k.
    Training poses may rank supports; held-out poses MUST NOT enter this call.
    Dynamic approximation is restricted to cardinality conflicts and needs
    independent probe validation downstream before writeback.
    """
    p = policy(value); w = np.asarray(initial, float); regions = np.asarray(regions, int)
    budgets = np.asarray(budgets, float); fixed = np.asarray(fixed, bool)
    allowed = np.asarray(allowed, bool); n, b = w.shape
    if fixed.shape != w.shape or allowed.shape != w.shape or budgets.shape[0] != n:
        raise ValueError('Support input shape mismatch')
    if np.any(w < 0) or not np.isfinite(w).all() or np.max(abs(w.sum(1)-1)) > 1e-6:
        raise ValueError('Support selection requires normalized weights')
    for r in range(budgets.shape[1]):
        if np.max(abs(w[:, regions == r].sum(1)-budgets[:, r])) > 1e-6:
            raise ValueError('Support selection budget mismatch')
    active = np.ones(n, bool) if selected is None else np.isin(np.arange(n), selected)
    seed = w.copy(); support = allowed.copy(); exceptions = []; compressed = []
    if not p['max_influences']:
        return seed, support, dict(audit(seed, p), exceptions=[], compressed_vertices=[])
    limits = np.ones(n) if delta_limits is None else np.asarray(delta_limits, float)
    if limits.shape != (n,) or np.any(limits < 0) or not np.isfinite(limits).all():
        raise ValueError('Invalid support correction bounds')
    pw = None
    if matrices is not None:
        pw = np.ones(len(matrices)) if pose_weights is None else np.asarray(pose_weights, float)
        if np.any(pw < 0) or not np.isfinite(pw).all() or pw.sum() <= 0: raise ValueError('Invalid support pose weights')
        pw = pw / pw.sum()
    span = max(float(np.linalg.norm(np.ptp(rest, axis=0))), 1e-6) if rest is not None else 1.
    for v in range(n):
        if not active[v]:
            support[v] = w[v] > 0
            if np.count_nonzero(w[v]) > 4: exceptions.append(dict(vertex=v, reason='protected_exterior'))
            continue
        frozen = np.where(fixed[v], w[v], 0.)
        pool = set(np.flatnonzero(allowed[v] & ~fixed[v] & (budgets[v, regions] > 0)))
        residual = np.bincount(regions, weights=np.where(fixed[v],0.,w[v]), minlength=budgets.shape[1])
        # Fixed finger weights are subtracted first, avoiding a spurious extra slot.
        needed = int(np.count_nonzero(residual > 0))
        slots = 4-int(np.count_nonzero(frozen))
        reason = 'fixed_and_category_lower_bound'
        if slots < needed and p['compress_dynamic']:
            dyn = np.flatnonzero((regions == 5) & (frozen > 0))
            keep_count = 4-needed-(np.count_nonzero(frozen)-len(dyn))
            if keep_count > 0 and len(dyn) > keep_count and rest is not None and dynamic_train is not None:
                ranked = sorted(dyn, key=lambda j: (-frozen[j], int(j)))
                proposals = list(itertools.islice(itertools.combinations(ranked, keep_count), 64))
                best = None
                for kept in proposals:
                    test = frozen.copy(); test[dyn] = 0
                    test[list(kept)] = frozen[list(kept)] * frozen[dyn].sum()/frozen[list(kept)].sum()
                    if np.max(abs(test[fixed[v]]-w[v, fixed[v]]), initial=0) > limits[v]+1e-10: continue
                    error = _dynamic_error(rest[v], test-frozen, dynamic_train, dynamic_scale)
                    if best is None or error < best[0]: best = (error, test)
                if best and best[0] <= p['dynamic_error_limit']:
                    frozen = best[1]; slots = 4-int(np.count_nonzero(frozen))
                else: reason = 'dynamic_training_response_failed'
            else: reason = 'dynamic_probe_or_slot_unavailable'
        def fail(why):
            support[v] = w[v] > 0
            exceptions.append(dict(vertex=v, reason=why))
        if slots < needed: fail(reason); continue
        if any(residual[r] > 0 and not any(regions[j] == r for j in pool) for r in range(len(residual))):
            fail('missing_category_candidates'); continue
        # Use centered skinning features for stable ranking across world offsets.
        h = np.eye(b)*max(prior, 1e-8); rhs = max(prior, 1e-8)*(w[v] if weight_prior is None else weight_prior[v])
        if matrices is not None:
            a = np.einsum('pbij,j->pbi', matrices[..., :3, :3], rest[v])+matrices[..., :3, 3]
            target = reference[:, v]-a[:, 0]; a = a-a[:, :1]
            h += np.einsum('pbi,pci,p->bc', a, a, pw)/span**2
            rhs += np.einsum('pbi,pi,p->b', a, target, pw)/span**2
        if objective is not None:
            h += objective[0][v]; rhs += objective[1][v]
        def evaluate(ids):
            if any(residual[r]>0 and not any(regions[j]==r for j in ids) for r in range(len(residual))):return None
            candidate = _fit(ids, w[v], frozen, regions, budgets[v], h, rhs, limits[v])
            if candidate is None: return None
            return float(candidate@h@candidate-2*rhs@candidate), candidate
        chosen = set(np.flatnonzero((w[v] > 0) & ~fixed[v])) & pool
        for r in np.flatnonzero(residual > 0):
            if not any(regions[j] == r for j in chosen):
                chosen.add(max((j for j in pool if regions[j] == r), key=lambda j: (w[v,j], -j)))
        fit = evaluate(chosen)
        while len(chosen) > slots:
            trials = [(evaluate(chosen-{j}), j) for j in sorted(chosen)]
            trials = [(trial, j) for trial, j in trials if trial is not None]
            if not trials: fit = None; break
            fit, dropped = min(trials, key=lambda x: (x[0][0], x[1])); chosen.remove(dropped)
        if fit is None: fail('support_or_local_bounds_infeasible'); continue
        # Bounded one-exchange search admits nearby candidates even when initially zero.
        evaluations = 0
        for incoming in sorted(pool-chosen, key=lambda j: (-w[v,j], j)):
            variants = [chosen|{incoming}] if len(chosen) < slots else [chosen-{j}|{incoming} for j in sorted(chosen)]
            for trial_ids in variants:
                trial = evaluate(trial_ids); evaluations += 1
                if trial is not None and trial[0] < fit[0]-1e-12: fit, chosen = trial, trial_ids
                if evaluations >= 64: break
            if evaluations >= 64: break
        seed[v] = fit[1]; support[v] = False; support[v, list(chosen)] = True
        support[v] |= frozen > 0
        if np.any(seed[v, fixed[v]]!=w[v, fixed[v]]): compressed.append(v)
    report = dict(audit(seed, p), exceptions=exceptions, compressed_vertices=compressed,
                  dynamic_weight_max_change=float(np.max(abs(seed[:,regions==5]-w[:,regions==5]),initial=0)),
                  search='bounded removal/exchange with regional feasible fits',
                  requires_independent_dynamic_validation=bool(compressed))
    return seed, support, report


def validate_result(initial, weights, regions, budgets, fixed, allowed, value=None, *,
                    selected=None, delta_limits=None, rest=None, dynamic_holdout=None, dynamic_scale=1.):
    """Independent full-mesh constraints; exception rows must remain byte-identical."""
    p = policy(value); w = np.asarray(weights); old = np.asarray(initial)
    result = audit(w, p); regions = np.asarray(regions)
    if w.shape != old.shape: raise ValueError('Wrong influence shape')
    fixed = np.asarray(fixed, bool); allowed = np.asarray(allowed, bool)
    change = (w!=old) if p['max_influences'] else (abs(w-old)>1e-8)
    dynamic_change = change & fixed & (regions[None, :] == 5)
    changed = np.flatnonzero(dynamic_change.any(1))
    compression=bool(p['max_influences'] and p['compress_dynamic'])
    immutable = fixed & ~(regions[None, :] == 5) if compression else fixed
    fixed_ok = not np.any(change & immutable)
    errors = []
    for v in changed:
        errors.append(_dynamic_error(rest[v], np.where(regions == 5, w[v]-old[v], 0), dynamic_holdout, dynamic_scale)
                      if rest is not None else float('inf'))
    dynamic_ok = not len(changed) or (compression and max(errors) <= p['dynamic_error_limit'])
    # Approximation cannot invent a dynamic influence or expand its original support.
    dynamic_ok &= not np.any((w > 0) & (old == 0) & fixed & (regions[None, :] == 5))
    for v in changed:
        residual=np.bincount(regions,weights=np.where(fixed[v],0.,old[v]),minlength=budgets.shape[1])
        dynamic_ok &= int(np.count_nonzero(old[v,fixed[v]]))+int(np.count_nonzero(residual))>4
    exceptions = np.asarray(result['over_limit_vertices'], int)
    exception_ok = bool(not len(exceptions) or np.array_equal(w[exceptions], old[exceptions]))
    outside = np.array([], int) if selected is None else np.setdiff1d(np.arange(len(w)), selected)
    local_ok = np.array_equal(w[outside], old[outside])
    if delta_limits is not None: local_ok &= bool(np.all(abs(w-old) <= np.asarray(delta_limits)[:,None]+1e-7))
    budget_error = max(float(np.max(abs(w[:,regions==r].sum(1)-budgets[:,r]))) for r in range(budgets.shape[1]))
    presence_ok=all(np.array_equal(w[:,regions==r].sum(1)>0,budgets[:,r]>0) for r in range(budgets.shape[1])) if p['max_influences'] else True
    result.update(fixed_ok=bool(fixed_ok), dynamic_response_ok=bool(dynamic_ok),
                  dynamic_changed_vertices=changed.tolist(), dynamic_holdout_max_error=(max(errors, default=0.) if all(np.isfinite(errors)) else None),
                  exceptions_unchanged=exception_ok, max_budget_error=budget_error, category_presence_ok=presence_ok,
                  constraints_ok=bool(fixed_ok and dynamic_ok and exception_ok and local_ok and presence_ok and budget_error < 1e-6
                                      and np.max(abs(w.sum(1)-1)) < 1e-6 and not np.any((w>0)&~(allowed|fixed))))
    return result
