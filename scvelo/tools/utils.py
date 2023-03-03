import warnings

import matplotlib.pyplot as pl
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix, issparse

from scvelo.core import l2_norm, prod_sum, sum

warnings.simplefilter("ignore")


# TODO: Add docstrings
def round(k, dec=2, as_str=None):
    """TODO."""
    if isinstance(k, (list, tuple, np.record, np.ndarray)):
        return [round(ki, dec) for ki in k]
    if "e" in f"{k}":
        k_str = f"{k}".split("e")
        result = f"{np.round(float(k_str[0]), dec)}1e{k_str[1]}"
        return f"{result}" if as_str else float(result)
    result = np.round(float(k), dec)
    return f"{result}" if as_str else result


# TODO: Add docstrings
def mean(x, axis=0):
    """TODO."""
    return x.mean(axis).A1 if issparse(x) else x.mean(axis)


# TODO: Add docstrings
def make_dense(X):
    """TODO."""
    XA = X.A if issparse(X) and X.ndim == 2 else X.A1 if issparse(X) else X
    if XA.ndim == 2:
        XA = XA[0] if XA.shape[0] == 1 else XA[:, 0] if XA.shape[1] == 1 else XA
    return np.array(XA)


# TODO: Add docstrings
def R_squared(residual, total):
    """TODO."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r2 = np.ones(residual.shape[1]) - prod_sum(
            residual, residual, axis=0
        ) / prod_sum(total, total, axis=0)
    r2[np.isnan(r2)] = 0
    return r2


# TODO: Add docstrings
def cosine_correlation(dX, Vi):
    """TODO."""
    dx = dX - dX.mean(-1)[:, None]
    Vi_norm = l2_norm(Vi, axis=0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if Vi_norm == 0:
            result = np.zeros(dx.shape[0])
        else:
            result = (
                np.einsum("ij, j", dx, Vi) / (l2_norm(dx, axis=1) * Vi_norm)[None, :]
            )
    return result


# TODO: Add docstrings
def normalize(X):
    """TODO."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if issparse(X):
            return X.multiply(csr_matrix(1.0 / np.abs(X).sum(1)))
        else:
            return X / X.sum(1)


# TODO: Add docstrings
def scale(X, min=0, max=1):
    """TODO."""
    idx = np.isfinite(X)
    if any(idx):
        X = X - X[idx].min() + min
        xmax = X[idx].max()
        X = X / xmax * max if xmax != 0 else X * max
    return X


# TODO: Add docstrings
def get_indices(dist, n_neighbors=None, mode_neighbors="distances"):
    """TODO."""
    from scvelo.preprocessing.neighbors import compute_connectivities_umap

    D = dist.copy()
    D.data += 1e-6

    n_counts = sum(D > 0, axis=1)
    n_neighbors = (
        n_counts.min() if n_neighbors is None else min(n_counts.min(), n_neighbors)
    )
    rows = np.where(n_counts > n_neighbors)[0]
    cumsum_neighs = np.insert(n_counts.cumsum(), 0, 0)
    dat = D.data

    for row in rows:
        n0, n1 = cumsum_neighs[row], cumsum_neighs[row + 1]
        rm_idx = n0 + dat[n0:n1].argsort()[n_neighbors:]
        dat[rm_idx] = 0
    D.eliminate_zeros()

    D.data -= 1e-6
    if mode_neighbors == "distances":
        indices = D.indices.reshape((-1, n_neighbors))
    elif mode_neighbors == "connectivities":
        knn_indices = D.indices.reshape((-1, n_neighbors))
        knn_distances = D.data.reshape((-1, n_neighbors))
        _, conn = compute_connectivities_umap(
            knn_indices, knn_distances, D.shape[0], n_neighbors
        )
        indices = get_indices_from_csr(conn)
    return indices, D


# TODO: Add docstrings
def get_indices_from_csr(conn):
    """TODO."""
    # extracts indices from connectivity matrix, pads with nans
    ixs = np.ones((conn.shape[0], np.max((conn > 0).sum(1)))) * np.nan
    for i in range(ixs.shape[0]):
        cell_indices = conn[i, :].indices
        ixs[i, : len(cell_indices)] = cell_indices
    return ixs


# TODO: Add docstrings
def get_iterative_indices(
    indices,
    index,
    n_recurse_neighbors=2,
    max_neighs=None,
):
    """TODO."""

    def iterate_indices(indices, index, n_recurse_neighbors):
        if n_recurse_neighbors > 1:
            index = iterate_indices(indices, index, n_recurse_neighbors - 1)
        ix = np.append(index, indices[index])  # direct and indirect neighbors
        if np.isnan(ix).any():
            ix = ix[~np.isnan(ix)]
        return ix.astype(int)

    indices = np.unique(iterate_indices(indices, index, n_recurse_neighbors))
    if max_neighs is not None and len(indices) > max_neighs:
        indices = np.random.choice(indices, max_neighs, replace=False)
    return indices


# TODO: Add docstrings
def geometric_matrix_sum(C, n_power=2):  # computes C + C^2 + C^3 + ...
    """TODO."""
    C_n = (
        geometric_matrix_sum(C, n_power - 1) if n_power > 2 else C if n_power > 1 else 0
    )
    return C + C.dot(C_n)


# TODO: Add docstrings
def groups_to_bool(adata, groups, groupby=None):
    """TODO."""
    groups = [groups] if isinstance(groups, str) else groups
    if isinstance(groups, (list, tuple, np.ndarray, np.record)):
        groupby = (
            groupby
            if groupby in adata.obs.keys()
            else "clusters"
            if "clusters" in adata.obs.keys()
            else "louvain"
            if "louvain" in adata.obs.keys()
            else None
        )
        if groupby is not None:
            groups = np.array([key in groups for key in adata.obs[groupby]])
        else:
            raise ValueError("groupby attribute not valid.")
    return groups


# TODO: Add docstrings
def most_common_in_list(lst):
    """TODO."""
    lst = [item for item in lst if item is not np.nan and item != "nan"]
    lst = list(lst)
    return max(set(lst), key=lst.count)


# TODO: Add docstrings
def randomized_velocity(adata, vkey="velocity", add_key="velocity_random"):
    """TODO."""
    V_rnd = adata.layers[vkey].copy()
    for i in range(V_rnd.shape[1]):
        np.random.shuffle(V_rnd[:, i])
        V_rnd[:, i] = V_rnd[:, i] * np.random.choice(
            np.array([+1, -1]), size=V_rnd.shape[0]
        )
    adata.layers[add_key] = V_rnd

    from .velocity_embedding import velocity_embedding
    from .velocity_graph import velocity_graph

    velocity_graph(adata, vkey=add_key)
    velocity_embedding(adata, vkey=add_key, autoscale=False)


# TODO: Add docstrings
def extract_int_from_str(array):
    """TODO."""

    def str_to_int(item):
        num = "".join(filter(str.isdigit, item))
        num = int(num) if len(num) > 0 else -1
        return num

    if isinstance(array, str):
        nums = str_to_int(array)
    elif len(array) > 1 and isinstance(array[0], str):
        nums = []
        for item in array:
            nums.append(str_to_int(item))
    else:
        nums = array
    nums = pd.Categorical(nums) if array.dtype == "category" else np.array(nums)
    return nums


# TODO: Finish docstrings
def strings_to_categoricals(adata):
    """Transform string annotations to categoricals."""
    from pandas import Categorical
    from pandas.api.types import is_bool_dtype, is_integer_dtype, is_string_dtype

    def is_valid_dtype(values):
        return (
            is_string_dtype(values) or is_integer_dtype(values) or is_bool_dtype(values)
        )

    df = adata.obs
    df_keys = [key for key in df.columns if is_valid_dtype(df[key])]
    for key in df_keys:
        c = df[key]
        c = Categorical(c)
        if 1 < len(c.categories) < min(len(c), 100):
            df[key] = c

    df = adata.var
    df_keys = [key for key in df.columns if is_string_dtype(df[key])]
    for key in df_keys:
        c = df[key].astype("U")
        c = Categorical(c)
        if 1 < len(c.categories) < min(len(c), 100):
            df[key] = c


# TODO: Add docstrings
def merge_groups(adata, key, map_groups, key_added=None, map_colors=None):
    """TODO."""
    strings_to_categoricals(adata)
    if len(map_groups) != len(adata.obs[key].cat.categories):
        map_coarse = {}
        for c in adata.obs[key].cat.categories:
            for group in map_groups:
                if any(cluster == c for cluster in map_groups[group]):
                    map_coarse[c] = group
            if c not in map_coarse:
                map_coarse[c] = c
        map_groups = map_coarse

    if key_added is None:
        key_added = f"{key}_coarse"

    from pandas.api.types import CategoricalDtype

    adata.obs[key_added] = adata.obs[key].map(map_groups).astype(CategoricalDtype())
    old_categories = adata.obs[key].cat.categories
    new_categories = adata.obs[key_added].cat.categories

    # map_colors is passed
    if map_colors is not None:
        old_colors = None
        if f"{key}_colors" in adata.uns:
            old_colors = adata.uns[f"{key}_colors"]
        new_colors = []
        for group in adata.obs[key_added].cat.categories:
            if group in map_colors:
                new_colors.append(map_colors[group])
            elif group in old_categories and old_colors is not None:
                new_colors.append(old_colors[old_categories.get_loc(group)])
            else:
                raise ValueError(f"You didn't specify a color for {group}.")
        adata.uns[f"{key_added}_colors"] = new_colors

    # map_colors is not passed
    elif f"{key}_colors" in adata.uns:
        old_colors = adata.uns[f"{key}_colors"]
        inverse_map_groups = {g: [] for g in new_categories}
        for old_group in old_categories:
            inverse_map_groups[map_groups[old_group]].append(old_group)
        new_colors = []
        for group in new_categories:
            # take the largest of the old groups
            old_group = (
                adata.obs[key][adata.obs[key].isin(inverse_map_groups[group])]
                .value_counts()
                .index[0]
            )
            new_colors.append(old_colors[old_categories.get_loc(old_group)])
        adata.uns[f"{key_added}_colors"] = new_colors


# TODO: Add docstrings
def cutoff_small_velocities(
    adata, vkey="velocity", key_added="velocity_cut", frac_of_max=0.5, use_raw=False
):
    """TODO."""
    x = adata.layers["spliced"] if use_raw else adata.layers["Ms"]
    y = adata.layers["unspliced"] if use_raw else adata.layers["Mu"]

    x_max = x.max(0).A[0] if issparse(x) else x.max(0)
    y_max = y.max(0).A[0] if issparse(y) else y.max(0)

    xy_norm = x / np.clip(x_max, 1e-3, None) + y / np.clip(y_max, 1e-3, None)
    W = xy_norm >= np.percentile(xy_norm, 98, axis=0) * frac_of_max

    adata.layers[key_added] = csr_matrix(W).multiply(adata.layers[vkey]).tocsr()

    from .velocity_embedding import velocity_embedding
    from .velocity_graph import velocity_graph

    velocity_graph(adata, vkey=key_added, approx=True)
    velocity_embedding(adata, vkey=key_added)


# TODO: Add docstrings
def make_unique_list(key, allow_array=False):
    """TODO."""
    from pandas import Index, unique

    if isinstance(key, Index):
        key = key.tolist()
    is_list = (
        isinstance(key, (list, tuple, np.record))
        if allow_array
        else isinstance(key, (list, tuple, np.ndarray, np.record))
    )
    is_list_of_str = is_list and all(isinstance(item, str) for item in key)
    return (
        unique(key) if is_list_of_str else key if is_list and len(key) < 20 else [key]
    )


# TODO: Finish docstrings
def test_bimodality(x, bins=30, kde=True, plot=False):
    """Test for bimodal distribution."""
    from scipy.stats import gaussian_kde, norm

    lb, ub = np.min(x), np.percentile(x, 99.9)
    grid = np.linspace(lb, ub if ub <= lb else np.max(x), bins)
    kde_grid = (
        gaussian_kde(x)(grid) if kde else np.histogram(x, bins=grid, density=True)[0]
    )

    idx = int(bins / 2) - 2
    end = idx + 4
    idx += np.argmin(kde_grid[idx:end])

    peak_0 = kde_grid[:idx].argmax()
    peak_1 = kde_grid[idx:].argmax()
    kde_peak = kde_grid[idx:][
        peak_1
    ]  # min(kde_grid[:idx][peak_0], kde_grid[idx:][peak_1])
    kde_mid = kde_grid[idx:].mean()  # kde_grid[idx]

    t_stat = (kde_peak - kde_mid) / np.clip(np.std(kde_grid) / np.sqrt(bins), 1, None)
    p_val = norm.sf(t_stat)

    grid_0 = grid[:idx]
    grid_1 = grid[idx:]
    means = [
        (grid_0[peak_0] + grid_0[min(peak_0 + 1, len(grid_0) - 1)]) / 2,
        (grid_1[peak_1] + grid_1[min(peak_1 + 1, len(grid_1) - 1)]) / 2,
    ]

    if plot:
        color = "grey"
        if kde:
            pl.plot(grid, kde_grid, color=color)
            pl.fill_between(grid, 0, kde_grid, alpha=0.4, color=color)
        else:
            pl.hist(x, bins=grid, alpha=0.4, density=True, color=color)
        pl.axvline(means[0], color=color)
        pl.axvline(means[1], color=color)
        pl.axhline(kde_mid, alpha=0.2, linestyle="--", color=color)
        pl.show()

    return t_stat, p_val, means  # ~ t_test (reject unimodality if t_stat > 3)


# TODO: Add docstrings
def random_subsample(adata, fraction=0.1, return_subset=False, copy=False):
    """TODO."""
    adata_sub = adata.copy() if copy else adata
    p, size = fraction, adata.n_obs
    subset = np.random.choice([True, False], size=size, p=[p, 1 - p])
    adata_sub._inplace_subset_obs(subset)
    return adata_sub if copy else subset if return_subset else None


# TODO: Add docstrings
def get_duplicates(array):
    """TODO."""
    from collections import Counter

    return np.array([item for (item, count) in Counter(array).items() if count > 1])


# TODO: Add docstrings
def corrcoef(x, y, mode="pearsons"):
    """TODO."""
    from scipy.stats import pearsonr, spearmanr

    corr, _ = spearmanr(x, y) if mode == "spearmans" else pearsonr(x, y)
    return corr


def vcorrcoef(X, y, mode="pearsons", axis=-1):
    """Pearsons/Spearmans correlation coefficients.

    Use Pearsons / Spearmans to test for linear / monotonic relationship.

    Arguments:
    ---------
    X: `np.ndarray`
        Data vector or matrix
    y: `np.ndarray`
        Data vector or matrix
    mode: 'pearsons' or 'spearmans' (default: `'pearsons'`)
        Which correlation metric to use.
    """
    if issparse(X):
        X = np.array(X.A)
    if issparse(y):
        y = np.array(y.A)
    if axis == 0:
        if X.ndim > 1:
            X = np.array(X.T)
        if y.ndim > 1:
            y = np.array(y.T)
    if X.shape[axis] != y.shape[axis]:
        X = X.T
    if mode in {"spearmans", "spearman"}:
        from scipy.stats.stats import rankdata

        X = np.apply_along_axis(rankdata, axis=-1, arr=X)
        y = np.apply_along_axis(rankdata, axis=-1, arr=y)
    Xm = np.array(X - (np.nanmean(X, -1)[:, None] if X.ndim > 1 else np.nanmean(X, -1)))
    ym = np.array(y - (np.nanmean(y, -1)[:, None] if y.ndim > 1 else np.nanmean(y, -1)))
    corr = np.nansum(Xm * ym, -1) / np.sqrt(
        np.nansum(Xm**2, -1) * np.nansum(ym**2, -1)
    )
    return corr


# TODO: Add docstrings
def isin(x, y):
    """TODO."""
    return np.array(pd.DataFrame(x).isin(y)).flatten()


# TODO: Add docstrings
def indices_to_bool(indices, n):
    """TODO."""
    return isin(np.arange(n), indices)


# TODO: Add docstrings
def convolve(adata, x):
    """TODO."""
    from scvelo.preprocessing.neighbors import get_connectivities

    conn = get_connectivities(adata)
    if isinstance(x, str) and x in adata.layers.keys():
        x = adata.layers[x]
    if x.ndim == 1:
        return conn.dot(x)
    idx_valid = ~np.isnan(x.sum(0))
    Y = np.ones(x.shape) * np.nan
    Y[:, idx_valid] = conn.dot(x[:, idx_valid])
    return Y


# TODO: Finish docstrings
def get_extrapolated_state(adata, vkey="velocity", dt=1, use_raw=None, dropna=True):
    """Get extrapolated cell state."""
    S = adata.layers["spliced" if use_raw else "Ms"]
    if dropna:
        St = S + dt * adata.layers[vkey]
        St = St[:, np.isfinite(np.sum(St, 0))]
    else:
        St = S + dt * np.nan_to_num(adata.layers[vkey])
    return St


# TODO: Add docstrings
# TODO: Generalize to use arbitrary modality i.e., not only layers
def get_plasticity_score(adata, modality="Ms"):
    """TODO."""
    idx_top_genes = np.argsort(adata.var["gene_count_corr"].values)[::-1][:200]
    Ms = np.array(adata.layers[modality][:, idx_top_genes])
    return scale(np.mean(Ms / np.max(Ms, axis=0), axis=1))
