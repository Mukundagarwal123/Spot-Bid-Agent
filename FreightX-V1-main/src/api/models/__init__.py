"""
FreightX multi-model carrier ranking package.

Models:
    model1 - FreightX historical lane dataset (exact zip+equipment match)
    model2 - Pure HQ proximity (no lane-specific tail filters)
    model3 - Pure entropy sorting + lane-specific tail filters
    model4 - Pure inspection count sorting + lane-specific tail filters
    model5 - Full mix model (always route-county restriction)

combine_model - Orchestrates all models with shared lane context
"""
