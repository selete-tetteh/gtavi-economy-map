# GTA VI Economy Map

A data analytics portfolio project predicting GTA VI launch pricing using
historical Rockstar Games pricing data, US CPI inflation data, and
Take-Two Interactive financials.

## Prediction

- **Base Edition: $69.72** (confidence range: $67.37 – $72.07)
- **Premium Edition: $93.05**

Prediction made April 2026, before GTA VI launch. To be verified on release.

## Key Findings

- AAA games held flat at $59.99 nominal for 13 years (2007–2019)
- In real terms, a $59.99 game in 2007 cost the equivalent of $93 today
- The jump to $69.99 in 2020 still left games cheaper in real terms than 2007
- All five major publishers converged on the same pricing shift by 2023

## Dataset

42 AAA game titles across 5 publishers (2007–2023):
Activision, EA, Nintendo, Rockstar Games, Sony

## Tech Stack

- Python 3.11
- MySQL 8.0 — data storage and source of truth
- pandas, scikit-learn — data processing and regression model
- matplotlib — visualisation
- Streamlit — interactive dashboard
- BLS public API — live CPI data
- SEC EDGAR / Macrotrends — Take-Two financials

## Methodology

Linear regression with Leave-One-Out cross-validation.
All prices inflation-adjusted to 2025 dollars using US CPI.
Model R-squared (LOO): 0.667 | MAE: $2.26 in 2025 dollar terms.

## Data Sources

- SteamSpy / VGInsights — historical game pricing
- US Bureau of Labor Statistics — CPI data (api.bls.gov)
- Macrotrends / SEC EDGAR — Take-Two Interactive financials

## Running Locally

```bash
conda env create -f environment.yml
conda activate gtavi-economy-map
python src/collect_game_prices.py
python src/collect_cpi_data.py
python src/collect_taketwo_financials.py
python src/clean_data.py
streamlit run app.py
```

## Project Structure
gtavi-economy-map/ 
├── data/ 
│ ├── raw/ 
│ └── processed/ 
├── notebooks/ # Development notebooks 
├── src/ # Production scripts
├── app.py # Streamlit dashboard
├── environment.yml 
└── README.md

## Model Limitations

42 data points is adequate but not large. The model learns industry-wide
pricing trends, not Rockstar-specific behaviour. Rockstar has never released
a mainline GTA at $69.99 — the prediction reflects where the industry average
sits. The confidence interval is intentionally honest about this uncertainty.
