# Analytics Roadmap

ChronoRoute's data science layer starts with explainable baselines before adding more complex models.

## Forecasting

Baseline demand forecasts use rolling averages or service-zone-hour averages. This is easy to explain and gives a benchmark for future models.

## Recommendations

The first recommendation system ranks repositioning moves from dropoff-surplus zones to pickup-pressure zones. Confidence is based on the strength of surplus and demand pressure.

## Simulation

The first simulation estimates before-vs-after imbalance reduction for a selected month, service, hour, and taxi count.

## Evaluation

Evaluation starts with MAE and RMSE when actuals and forecasts are both available.

## Future Work

- Backtesting by service and borough.
- Weather/event/calendar features.
- Route-aware repositioning costs.
- H3-based spatial models.
- Frontend views for service comparison and recommendation review.
