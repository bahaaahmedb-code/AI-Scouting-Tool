"""Similarity search for similar, cheaper players (notebook cells 35, 39, 45).

Changes agreed in the plan:
* D2: the price filter uses OUT-OF-FOLD estimates (target and candidates), not the listed value.
* D4: shared strengths = features where both players are above their position average (z > 0),
      ranked by the smaller of the two z-scores.
NEW: relaxation suggestions when a search returns no (or few) candidates.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

from .constants import GK_RADAR, GK_SIM_FEATURES, RADAR, SIM_FEATURES

ALL_SIM_FEATURES = list(dict.fromkeys(SIM_FEATURES + GK_SIM_FEATURES))
ALL_RADAR = list(dict.fromkeys(RADAR + GK_RADAR))


def position_zscores(d: pd.DataFrame) -> pd.DataFrame:
    """Each statistic converted to a z-score within the player's position.
    Goalkeepers use GK_SIM_FEATURES (with 0 on outfield-only cols); outfield players use SIM_FEATURES (with 0 on GK-only cols).
    """
    Z = pd.DataFrame(0.0, index=d.index, columns=ALL_SIM_FEATURES)
    out_mask = d["position"] != "G"
    gk_mask = d["position"] == "G"
    if out_mask.any():
        Z.loc[out_mask, SIM_FEATURES] = (
            d.loc[out_mask].groupby("position")[SIM_FEATURES].transform(lambda s: (s - s.mean()) / s.std()).fillna(0.0)
        )
    if gk_mask.any():
        Z.loc[gk_mask, GK_SIM_FEATURES] = (
            d.loc[gk_mask, GK_SIM_FEATURES].apply(lambda s: (s - s.mean()) / s.std()).fillna(0.0)
        )
        # Invert goals_conceded_p90 so fewer goals conceded is a positive z-score strength
        if "goals_conceded_p90" in Z.columns:
            Z.loc[gk_mask, "goals_conceded_p90"] = -Z.loc[gk_mask, "goals_conceded_p90"]
    return Z


def similarity_matrix(Z: pd.DataFrame) -> np.ndarray:
    return cosine_similarity(Z.to_numpy())


def radar_percentiles(d: pd.DataFrame) -> pd.DataFrame:
    pct = d.groupby("position")[ALL_RADAR].rank(pct=True) * 100
    return pct


def shared_strengths(z_a: np.ndarray, z_b: np.ndarray, k: int = 3, pos: str | None = None) -> list[str]:
    both = np.minimum(z_a, z_b)
    order = np.argsort(-both)
    allowed = set(GK_SIM_FEATURES if pos == "G" else (SIM_FEATURES if pos in ("D", "M", "F") else ALL_SIM_FEATURES))
    out = [ALL_SIM_FEATURES[j] for j in order if both[j] > 0 and ALL_SIM_FEATURES[j] in allowed]
    return out[:k]


@dataclass
class ScoutQuery:
    target: int
    same_position: bool = True
    position: str | None = None          # explicit position filter (overrides same_position)
    max_pct: float = 60.0                # % of the target's out-of-fold estimate
    max_age: int | None = None
    min_age: int | None = None
    max_eur: float | None = None         # absolute cap (chatbot: "under 30 million")
    min_eur: float | None = None
    n: int = 10
    exclude: list[int] = field(default_factory=list)
    method: str = "neural"               # "neural" (PyTorch Autoencoder DNA) | "cosine" (z-score cosine)


def _mask(d: pd.DataFrame, q: ScoutQuery, value_col: str, max_pct, max_age, pos_mode) -> np.ndarray:
    t = d.loc[q.target]
    m = np.ones(len(d), dtype=bool)
    m[q.target] = False
    for e in q.exclude:
        m[e] = False
    if pos_mode == "explicit":
        m &= (d["position"] == q.position).to_numpy()
    elif pos_mode == "same":
        m &= (d["position"] == t["position"]).to_numpy()
    if max_pct is not None:
        m &= (d[value_col] <= max_pct / 100 * t[value_col]).to_numpy()
    if q.max_eur is not None:
        m &= (d[value_col] <= q.max_eur).to_numpy()
    if q.min_eur is not None:
        m &= (d[value_col] >= q.min_eur).to_numpy()
    if max_age is not None:
        m &= (d["age"] <= max_age).to_numpy()
    if q.min_age is not None:
        m &= (d["age"] >= q.min_age).to_numpy()
    return m


def _pos_mode(q: ScoutQuery) -> str:
    if q.position:
        return "explicit"
    return "same" if q.same_position else "any"


def scout(d: pd.DataFrame, Z: pd.DataFrame, S: np.ndarray, q: ScoutQuery, value_col: str = "oof_value_eur") -> dict:
    pos_mode = _pos_mode(q)
    m = _mask(d, q, value_col, q.max_pct, q.max_age, pos_mode)
    idx = np.flatnonzero(m)
    sims = S[q.target, idx]
    order = idx[np.argsort(-sims, kind="stable")][: q.n]
    zt = Z.iloc[q.target].to_numpy()
    tv = float(d.at[q.target, value_col])
    rows = []
    for rank, c in enumerate(order, 1):
        v = float(d.at[c, value_col])
        rows.append({
            "rank": rank, "id": int(c), "similarity": float(S[q.target, c]),
            "value_eur": v, "pct_of_target": v / tv * 100,
            "shared_strengths": shared_strengths(zt, Z.iloc[c].to_numpy()),
        })
    return {"n_passed": int(m.sum()), "results": rows, "pos_mode": pos_mode,
            "suggestions": relax_suggestions(d, q, value_col, int(m.sum())) if len(rows) < min(q.n, 3) else []}


def relax_suggestions(d: pd.DataFrame, q: ScoutQuery, value_col: str, n_now: int) -> list[dict]:
    """For each filter, the smallest relaxation that adds candidates, e.g. 'Raising the limit to 70% adds 4 candidates.'"""
    out = []
    pos_mode = _pos_mode(q)
    if q.max_pct is not None:
        for pct in range(int(q.max_pct) + 10, 201, 10):
            n = int(_mask(d, q, value_col, pct, q.max_age, pos_mode).sum())
            if n > n_now:
                out.append({"filter": "max_pct", "value": pct, "adds": n - n_now,
                            "text": f"Raising the price limit to {pct}% adds {n - n_now} candidate{'s' if n - n_now != 1 else ''}."})
                break
    if q.max_age is not None:
        for age in range(q.max_age + 1, 41):
            n = int(_mask(d, q, value_col, q.max_pct, age, pos_mode).sum())
            if n > n_now:
                out.append({"filter": "max_age", "value": age, "adds": n - n_now,
                            "text": f"Raising the age limit to {age} adds {n - n_now} candidate{'s' if n - n_now != 1 else ''}."})
                break
    if pos_mode != "any":
        n = int(_mask(d, q, value_col, q.max_pct, q.max_age, "any").sum())
        if n > n_now:
            out.append({"filter": "position", "value": "any", "adds": n - n_now,
                        "text": f"Allowing any position adds {n - n_now} candidate{'s' if n - n_now != 1 else ''}."})
    if q.max_eur is not None:
        n = int(_mask(d, ScoutQuery(**{**q.__dict__, "max_eur": None}), value_col, q.max_pct, q.max_age, pos_mode).sum())
        if n > n_now:
            out.append({"filter": "max_eur", "value": None, "adds": n - n_now,
                        "text": f"Removing the euro cap adds {n - n_now} candidate{'s' if n - n_now != 1 else ''}."})
    return out


def train_neural_embeddings(
    d: pd.DataFrame,
    Z: pd.DataFrame,
    hist_df: pd.DataFrame | None = None,
    gk_hist_df: pd.DataFrame | None = None,
    log=print,
) -> dict | None:
    """Train PyTorch Denoising Autoencoders ('Neural Player DNA') on historical Big-5
    player-seasons and encode all 299 EPL players into dense tactical embeddings.

    Imported lazily so runtime serving on Vercel requires zero PyTorch dependency.
    """
    try:
        import torch
        import torch.nn as nn
        from torch.utils.data import DataLoader, TensorDataset
    except ImportError:
        log("PyTorch not installed; skipping Neural Autoencoder embeddings.")
        return None

    torch.manual_seed(42)
    np.random.seed(42)

    class DenoisingAutoencoder(nn.Module):
        def __init__(self, in_dim: int, hidden_dim: int, latent_dim: int):
            super().__init__()
            self.encoder = nn.Sequential(
                nn.Linear(in_dim, hidden_dim),
                nn.LayerNorm(hidden_dim),
                nn.GELU(),
                nn.Dropout(0.15),
                nn.Linear(hidden_dim, latent_dim),
            )
            self.decoder = nn.Sequential(
                nn.Linear(latent_dim, hidden_dim),
                nn.LayerNorm(hidden_dim),
                nn.GELU(),
                nn.Linear(hidden_dim, in_dim),
            )

        def forward(self, x, corrupt: bool = False):
            x_in = x + 0.15 * torch.randn_like(x) if corrupt else x
            z = self.encoder(x_in)
            return self.decoder(z), z

    def _fit_ae(X_train: np.ndarray, X_eval: np.ndarray, hidden_dim: int, latent_dim: int, epochs: int = 45):
        in_dim = X_train.shape[1]
        model = DenoisingAutoencoder(in_dim, hidden_dim, latent_dim)
        opt = torch.optim.AdamW(model.parameters(), lr=2.5e-3, weight_decay=1e-4)
        loss_fn = nn.MSELoss()
        ds = TensorDataset(torch.tensor(X_train, dtype=torch.float32))
        dl = DataLoader(ds, batch_size=min(256, max(16, len(X_train) // 4)), shuffle=True)

        model.train()
        for _ in range(epochs):
            for (bx,) in dl:
                opt.zero_grad()
                recon, _ = model(bx, corrupt=True)
                loss = loss_fn(recon, bx)
                loss.backward()
                opt.step()

        model.eval()
        with torch.no_grad():
            tx = torch.tensor(X_eval, dtype=torch.float32)
            recon_e, emb_e = model(tx, corrupt=False)
            r_np = recon_e.numpy()
            ss_res = float(np.sum((X_eval - r_np) ** 2))
            ss_tot = float(np.sum((X_eval - X_eval.mean(axis=0)) ** 2)) or 1.0
            recon_r2 = max(0.0, 1.0 - ss_res / ss_tot)
            return emb_e.numpy(), round(recon_r2, 4)

    # 1. Outfield Autoencoder (trained on Big-5 historical outfield seasons + current outfield)
    out_mask = (d["position"] != "G").to_numpy()
    Z_out_cur = Z.loc[out_mask, SIM_FEATURES].to_numpy(dtype=np.float32)
    X_out_train = Z_out_cur
    if hist_df is not None and not hist_df.empty:
        h_out = hist_df[hist_df["position"].isin(["D", "M", "F"])].copy()
        avail = [c for c in SIM_FEATURES if c in h_out.columns]
        if len(avail) == len(SIM_FEATURES) and len(h_out) >= 200:
            if "minutes" in h_out.columns:
                h_out = h_out[h_out["minutes"] >= 600].copy()
            Z_hist_out = (
                h_out.groupby("position")[SIM_FEATURES]
                .transform(lambda s: (s - s.mean()) / (s.std() or 1.0))
                .fillna(0.0)
                .clip(-4.5, 4.5)
                .to_numpy(dtype=np.float32)
            )
            X_out_train = np.vstack([Z_hist_out, np.clip(Z_out_cur, -4.5, 4.5)])

    emb_out, out_recon_r2 = _fit_ae(X_out_train, np.clip(Z_out_cur, -4.5, 4.5), hidden_dim=32, latent_dim=16, epochs=40)

    # 2. Goalkeeper Autoencoder (trained on Big-5 historical GK seasons + current GKs)
    gk_mask = (d["position"] == "G").to_numpy()
    Z_gk_cur = Z.loc[gk_mask, GK_SIM_FEATURES].to_numpy(dtype=np.float32)
    X_gk_cur = np.clip(Z_gk_cur, -4.5, 4.5)
    X_gk_train = X_gk_cur
    if gk_hist_df is not None and not gk_hist_df.empty:
        avail_gk = [c for c in GK_SIM_FEATURES if c in gk_hist_df.columns]
        if len(avail_gk) == len(GK_SIM_FEATURES) and len(gk_hist_df) >= 50:
            h_gk = gk_hist_df[gk_hist_df["minutes"] >= 600].copy() if "minutes" in gk_hist_df.columns else gk_hist_df.copy()
            Z_hist_gk = h_gk[GK_SIM_FEATURES].apply(lambda s: (s - s.mean()) / (s.std() or 1.0)).fillna(0.0)
            if "goals_conceded_p90" in Z_hist_gk.columns:
                Z_hist_gk["goals_conceded_p90"] = -Z_hist_gk["goals_conceded_p90"]
            X_gk_train = np.vstack([Z_hist_gk.clip(-4.5, 4.5).to_numpy(dtype=np.float32), X_gk_cur])

    emb_gk, gk_recon_r2 = _fit_ae(X_gk_train, X_gk_cur, hidden_dim=16, latent_dim=8, epochs=60)

    # Build unified 299 x 299 neural similarity matrix (0 cross-regime similarity between GK and outfield)
    n_tot = len(d)
    S_neural = np.zeros((n_tot, n_tot), dtype=np.float64)
    out_idx = np.flatnonzero(out_mask)
    gk_idx = np.flatnonzero(gk_mask)
    if len(out_idx):
        S_out = cosine_similarity(emb_out)
        S_neural[np.ix_(out_idx, out_idx)] = S_out
    if len(gk_idx):
        S_gk = cosine_similarity(emb_gk)
        S_neural[np.ix_(gk_idx, gk_idx)] = S_gk

    meta = {
        "architecture": "PyTorch Denoising Autoencoder (LayerNorm + GELU + Dropout 0.15)",
        "outfield_dims": f"{len(SIM_FEATURES)} → 32 → 16 → 32 → {len(SIM_FEATURES)}",
        "gk_dims": f"{len(GK_SIM_FEATURES)} → 16 → 8 → 16 → {len(GK_SIM_FEATURES)}",
        "outfield_train_seasons": int(len(X_out_train)),
        "gk_train_seasons": int(len(X_gk_train)),
        "outfield_recon_r2": out_recon_r2,
        "gk_recon_r2": gk_recon_r2,
    }
    log(
        f"Trained PyTorch Denoising Autoencoder: outfield {meta['outfield_train_seasons']} seasons "
        f"(Recon R²={out_recon_r2:.3f}) | GK {meta['gk_train_seasons']} seasons (Recon R²={gk_recon_r2:.3f})"
    )
    return {"S_neural": S_neural, "emb_out": emb_out, "emb_gk": emb_gk, "meta": meta}
