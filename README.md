# MLB Prop App / StrikeOut King 9000

Streamlit entry point:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```

The repository is being migrated toward a two-path strikeout projection system:

- independent game simulation
- mathematical / gradient-boosted projection
- calibrated ensemble probabilities
- immutable pregame snapshots
- chronological walk-forward evaluation

Historical reconstruction must use only information that could have been known before first pitch. Current aggregate CSVs are reference data, not historical ground truth.
