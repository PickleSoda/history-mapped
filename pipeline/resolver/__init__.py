"""Geo-resolution — resolves entities to geographic references.

This package is the pipeline's decision-maker for auto-georesolution.
It queries external sources (OHM Nominatim, etc.) and emits a
`_geo_resolution` manifest dict for each entity.
"""
