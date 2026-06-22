# Macro Dashboard

FRED-based macro economic data pipeline and Streamlit dashboard.

## Setup

```
pip install -r requirements.txt
```

## Run locally

1. Set your FRED API key:
   - Windows cmd: `set FRED_API_KEY=your_key_here`
   - PowerShell: `$env:FRED_API_KEY="your_key_here"`

2. Pull data:
   ```
   python fred_pull.py
   ```

3. Launch dashboard:
   ```
   streamlit run app.py
   ```

## Streamlit Cloud deployment

Add to Settings → Secrets:
```
FRED_API_KEY = "your_key_here"
```

## Series covered
Rates/curve, inflation (CPI, PCE), labor, GDP, industrial production,
retail sales, consumer sentiment, housing starts, mortgage rates.
