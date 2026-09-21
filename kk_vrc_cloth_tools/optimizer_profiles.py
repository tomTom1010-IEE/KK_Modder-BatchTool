"""Shared, versioned baseline from the validated two-stage workflow.

These are starting values, not a guarantee for arbitrary garments or rigs.
"""
CONSERVATIVE_ID = 'conservative_v1'
MACRO = dict(prior=.002, smooth=.002, trust=.15, max_contact_steps=4)
TERMINAL = dict(prior=.00005, smooth=.00003, residual_scale=.15,
                trust=.35, max_contact_steps=8)
