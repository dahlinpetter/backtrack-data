# Backtrack train data

Delay data for commuter trains around the Öresund (Lund C – København H), collected for the Backtrack app.

- `data/delays.json`: recent departures and arrivals with delays (updated every 10 minutes on weekdays)
- `data/page_history.json`, `data/history.json`: history rebuilt from Trafiklab's KoDa archive (nightly)
- `data/trv/`: actual times from Trafikverket's open API for a few other lines (nightly)

Data: [Trafiklab.se](https://www.trafiklab.se) (CC-BY 4.0) and Trafikverket.

Needs these repository secrets: `TRAFIKLAB_KEY`, `KODA_KEY`, `TRAFIKVERKET_KEY`.
