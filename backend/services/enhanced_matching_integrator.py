"""Compatibility shim exposing EnhancedMatchingIntegrator name expected by tests.
Delegates to MatchingIntegrator in matching_integrator.py.
"""
from .matching_integrator import MatchingIntegrator as EnhancedMatchingIntegrator

__all__ = ["EnhancedMatchingIntegrator"]
