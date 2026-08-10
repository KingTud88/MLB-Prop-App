from pathlib import Path
p=Path("streamlit_app.py")
s=p.read_text(encoding="utf-8")
old='''class Projection:\n    mean_k:float; mean_outs:float; k_sd:float; outs_sd:float; k_probs:np.ndarray; outs_probs:np.ndarray; k_samples:np.ndarray; outs_samples:np.ndarray; confidence:str; quality:int; factors:list[tuple[str,float]]\n'''
new='''class Projection:\n    mean_k:float; mean_outs:float; k_sd:float; outs_sd:float; k_probs:np.ndarray; outs_probs:np.ndarray; k_samples:np.ndarray; outs_samples:np.ndarray; confidence:str; quality:int; factors:list[tuple[str,float]]; engine:ProjectionResult\n'''
if old not in s:
    raise SystemExit("Projection dataclass pattern not found")
p.write_text(s.replace(old,new,1),encoding="utf-8")
print("fixed Projection wrapper")
