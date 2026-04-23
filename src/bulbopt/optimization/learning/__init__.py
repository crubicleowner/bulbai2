"""Learning helpers for night-run optimization.

Modules:

* ``validity_classifier`` — logistic regression on accumulated HF history to
  predict whether a candidate's mesh will be invalid (self-intersecting,
  non-watertight, zero/negative volume). Used as a prefilter by the mid-gate
  so obviously broken candidates never reach the deformer (see design spec
  2026-04-23 §4 L4).
"""
