"""Plain-language explanations for route comparisons."""
def route_tradeoff(result):
    if result.shortest.edges == result.lowest_fuel.edges:
        return 'Both choices use the same route. There is no simulated fuel saving.'
    percent = result.fuel_saved_percent
    extra = result.lowest_fuel.distance_m - result.shortest.distance_m
    if percent is None:
        return 'The reference route has zero estimated fuel, so a percentage saving cannot be calculated.'
    if percent < 0.005:
        return 'Both choices have essentially the same simulated fuel use.'
    if extra > 1:
        return f'About {percent:.1f}% less simulated fuel for an extra {extra:,.0f} metres.'
    return f'About {percent:.1f}% less simulated fuel at essentially the same distance.'
